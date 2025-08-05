"""
Session Lock Manager for preventing conflicting server instances

This service provides session coordination to prevent multiple server instances
from running simultaneously and manages graceful session handover.
"""

import asyncio
import json
import logging
import os
import signal
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Session states"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    CRASHED = "crashed"
    ZOMBIE = "zombie"


@dataclass
class SessionInfo:
    """Information about a server session"""
    session_id: str
    pid: int
    host: str
    port: int
    state: SessionState
    started_at: datetime
    last_heartbeat: datetime
    process_name: str
    working_directory: str
    command_line: List[str]
    user: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['state'] = self.state.value
        data['started_at'] = self.started_at.isoformat()
        data['last_heartbeat'] = self.last_heartbeat.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionInfo':
        """Create from dictionary"""
        data = data.copy()
        data['state'] = SessionState(data['state'])
        data['started_at'] = datetime.fromisoformat(data['started_at'])
        data['last_heartbeat'] = datetime.fromisoformat(data['last_heartbeat'])
        return cls(**data)


class SessionLockManager:
    """Manages session locks to prevent conflicting server instances"""
    
    def __init__(self, lock_dir: Optional[str] = None):
        self.lock_dir = Path(lock_dir) if lock_dir else Path.home() / ".lifeboard" / "locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        
        self.lock_file = self.lock_dir / "server.lock"
        self.session_file = self.lock_dir / "session_info.json"
        
        # Configuration
        self.heartbeat_interval_seconds = 30
        self.stale_session_timeout_seconds = 300  # 5 minutes
        self.zombie_session_timeout_seconds = 900  # 15 minutes
        
        # Current session tracking
        self.current_session: Optional[SessionInfo] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self._shutdown_requested = False
        
    async def acquire_session_lock(self, host: str, port: int) -> Dict[str, Any]:
        """
        Acquire session lock for server startup
        
        Returns:
            Dict with 'success', 'session_id', and conflict information
        """
        logger.info(f"SESSION_LOCK: Attempting to acquire session lock for {host}:{port}")
        
        result = {
            'success': False,
            'session_id': None,
            'existing_session': None,
            'conflict_resolution': None,
            'recommendations': []
        }
        
        try:
            # Check for existing session
            existing_session = await self._check_existing_session()
            
            if existing_session:
                logger.info(f"SESSION_LOCK: Found existing session: {existing_session.session_id}")
                
                # Validate existing session
                session_status = await self._validate_session(existing_session)
                
                if session_status['is_valid']:
                    # Active session exists
                    result['existing_session'] = existing_session.to_dict()
                    result['conflict_resolution'] = await self._analyze_session_conflict(existing_session, host, port)
                    result['recommendations'] = self._generate_conflict_recommendations(existing_session, host, port)
                    
                    logger.warning(f"SESSION_LOCK: Active session exists, cannot acquire lock")
                    return result
                else:
                    # Stale/zombie session, can be cleaned up
                    logger.info(f"SESSION_LOCK: Existing session is {session_status['status']}, cleaning up...")
                    await self._cleanup_stale_session(existing_session)
            
            # Create new session
            session_id = self._generate_session_id()
            current_process = await self._get_current_process_info()
            
            new_session = SessionInfo(
                session_id=session_id,
                pid=os.getpid(),
                host=host,
                port=port,
                state=SessionState.STARTING,
                started_at=datetime.now(timezone.utc),
                last_heartbeat=datetime.now(timezone.utc),
                process_name=current_process['name'],
                working_directory=os.getcwd(),
                command_line=current_process['cmdline'],
                user=current_process['user']
            )
            
            # Write session lock
            await self._write_session_lock(new_session)
            
            # Start heartbeat
            self.current_session = new_session
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            result['success'] = True
            result['session_id'] = session_id
            
            logger.info(f"SESSION_LOCK: Successfully acquired session lock: {session_id}")
            
        except Exception as e:
            logger.error(f"SESSION_LOCK: Error acquiring session lock: {e}")
            result['error'] = str(e)
        
        return result
    
    async def release_session_lock(self) -> Dict[str, Any]:
        """Release the current session lock"""
        logger.info("SESSION_LOCK: Releasing session lock...")
        
        result = {'success': False, 'error': None}
        
        try:
            self._shutdown_requested = True
            
            # Stop heartbeat
            if self.heartbeat_task and not self.heartbeat_task.done():
                self.heartbeat_task.cancel()
                try:
                    await asyncio.wait_for(self.heartbeat_task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            
            # Update session state
            if self.current_session:
                self.current_session.state = SessionState.STOPPING
                await self._write_session_lock(self.current_session)
                
                # Wait a moment for any pending operations
                await asyncio.sleep(1)
                
                # Final state update
                self.current_session.state = SessionState.STOPPED
                await self._write_session_lock(self.current_session)
            
            # Remove lock files
            try:
                if self.lock_file.exists():
                    self.lock_file.unlink()
                if self.session_file.exists():
                    self.session_file.unlink()
            except Exception as cleanup_error:
                logger.warning(f"SESSION_LOCK: Error cleaning up lock files: {cleanup_error}")
            
            result['success'] = True
            logger.info("SESSION_LOCK: Session lock released successfully")
            
        except Exception as e:
            logger.error(f"SESSION_LOCK: Error releasing session lock: {e}")
            result['error'] = str(e)
        
        return result
    
    async def _check_existing_session(self) -> Optional[SessionInfo]:
        """Check if there's an existing session"""
        try:
            if not self.session_file.exists():
                return None
            
            with open(self.session_file, 'r') as f:
                session_data = json.load(f)
            
            return SessionInfo.from_dict(session_data)
            
        except Exception as e:
            logger.warning(f"SESSION_LOCK: Error reading existing session: {e}")
            return None
    
    async def _validate_session(self, session: SessionInfo) -> Dict[str, Any]:
        """Validate if a session is still active"""
        validation = {
            'is_valid': False,
            'status': 'unknown',
            'reason': None
        }
        
        try:
            # Check if process still exists
            try:
                os.kill(session.pid, 0)  # Signal 0 just checks if process exists
                process_exists = True
            except (OSError, ProcessLookupError):
                process_exists = False
                validation['status'] = 'process_dead'
                validation['reason'] = f'Process {session.pid} no longer exists'
                return validation
            
            # Check heartbeat freshness
            now = datetime.now(timezone.utc)
            heartbeat_age = (now - session.last_heartbeat).total_seconds()
            
            if heartbeat_age > self.zombie_session_timeout_seconds:
                validation['status'] = 'zombie'
                validation['reason'] = f'Heartbeat stale for {heartbeat_age:.1f}s (zombie threshold: {self.zombie_session_timeout_seconds}s)'
                return validation
            elif heartbeat_age > self.stale_session_timeout_seconds:
                validation['status'] = 'stale'
                validation['reason'] = f'Heartbeat stale for {heartbeat_age:.1f}s (stale threshold: {self.stale_session_timeout_seconds}s)'
                return validation
            
            # Session appears valid
            validation['is_valid'] = True
            validation['status'] = 'active'
            validation['heartbeat_age_seconds'] = heartbeat_age
            
        except Exception as e:
            logger.warning(f"SESSION_LOCK: Error validating session: {e}")
            validation['status'] = 'validation_error'
            validation['reason'] = str(e)
        
        return validation
    
    async def _analyze_session_conflict(self, existing_session: SessionInfo, 
                                       requested_host: str, requested_port: int) -> Dict[str, Any]:
        """Analyze the nature of session conflict"""
        conflict = {
            'type': 'unknown',
            'severity': 'medium',
            'can_resolve': False,
            'resolution_strategy': None
        }
        
        # Same port conflict
        if existing_session.port == requested_port:
            if existing_session.host == requested_host:
                conflict['type'] = 'exact_match'
                conflict['severity'] = 'high'
                conflict['resolution_strategy'] = 'terminate_existing'
            else:
                conflict['type'] = 'port_conflict'  
                conflict['severity'] = 'high'
                conflict['resolution_strategy'] = 'use_different_port'
        
        # Different port, same host
        elif existing_session.host == requested_host:
            conflict['type'] = 'host_overlap'
            conflict['severity'] = 'low'
            conflict['can_resolve'] = True
            conflict['resolution_strategy'] = 'allow_multiple'
        
        # Completely different
        else:
            conflict['type'] = 'separate_instance'
            conflict['severity'] = 'low'
            conflict['can_resolve'] = True
            conflict['resolution_strategy'] = 'allow_multiple'
        
        return conflict
    
    def _generate_conflict_recommendations(self, existing_session: SessionInfo,
                                         requested_host: str, requested_port: int) -> List[Dict[str, str]]:
        """Generate recommendations for resolving session conflicts"""
        recommendations = []
        
        if existing_session.port == requested_port:
            recommendations.append({
                'action': 'terminate_existing',
                'description': f'Terminate existing server process (PID: {existing_session.pid})',
                'command': f'kill {existing_session.pid}',
                'risk': 'medium'
            })
            
            recommendations.append({
                'action': 'use_different_port',
                'description': f'Start server on a different port (e.g., {requested_port + 1})',
                'command': f'--port {requested_port + 1}',
                'risk': 'low'
            })
        
        recommendations.append({
            'action': 'wait_for_shutdown',
            'description': 'Wait for existing server to shutdown naturally',
            'risk': 'low'
        })
        
        return recommendations
    
    async def _cleanup_stale_session(self, session: SessionInfo):
        """Clean up a stale or zombie session"""
        logger.info(f"SESSION_LOCK: Cleaning up stale session: {session.session_id}")
        
        try:
            # Try to terminate zombie process gracefully
            if session.state in [SessionState.ZOMBIE, SessionState.CRASHED]:
                try:
                    # Try SIGTERM first
                    os.kill(session.pid, signal.SIGTERM)
                    await asyncio.sleep(2)
                    
                    # Check if still alive, then SIGKILL
                    try:
                        os.kill(session.pid, 0)
                        os.kill(session.pid, signal.SIGKILL)
                        logger.info(f"SESSION_LOCK: Force killed zombie process {session.pid}")
                    except ProcessLookupError:
                        logger.info(f"SESSION_LOCK: Process {session.pid} terminated gracefully")
                        
                except ProcessLookupError:
                    logger.info(f"SESSION_LOCK: Process {session.pid} already gone")
                except PermissionError:
                    logger.warning(f"SESSION_LOCK: No permission to kill process {session.pid}")
            
            # Remove lock files
            for file_path in [self.lock_file, self.session_file]:
                try:
                    if file_path.exists():
                        file_path.unlink()
                except Exception as e:
                    logger.warning(f"SESSION_LOCK: Error removing {file_path}: {e}")
                    
        except Exception as e:
            logger.error(f"SESSION_LOCK: Error during session cleanup: {e}")
    
    async def _write_session_lock(self, session: SessionInfo):
        """Write session information to lock files"""
        try:
            # Write session info
            with open(self.session_file, 'w') as f:
                json.dump(session.to_dict(), f, indent=2)
            
            # Write simple lock file with PID
            with open(self.lock_file, 'w') as f:
                f.write(f"{session.pid}\n{session.session_id}\n")
                
        except Exception as e:
            logger.error(f"SESSION_LOCK: Error writing session lock: {e}")
            raise
    
    async def _heartbeat_loop(self):
        """Maintain session heartbeat"""
        logger.info("SESSION_LOCK: Starting heartbeat loop...")
        
        try:
            while not self._shutdown_requested:
                if self.current_session:
                    # Update heartbeat
                    self.current_session.last_heartbeat = datetime.now(timezone.utc)
                    self.current_session.state = SessionState.RUNNING
                    
                    await self._write_session_lock(self.current_session)
                    logger.debug(f"SESSION_LOCK: Heartbeat updated for session {self.current_session.session_id}")
                
                await asyncio.sleep(self.heartbeat_interval_seconds)
                
        except asyncio.CancelledError:
            logger.info("SESSION_LOCK: Heartbeat loop cancelled")
        except Exception as e:
            logger.error(f"SESSION_LOCK: Error in heartbeat loop: {e}")
    
    async def _get_current_process_info(self) -> Dict[str, Any]:
        """Get information about current process"""
        try:
            import sys
            import getpass
            
            return {
                'name': 'python',
                'cmdline': sys.argv,
                'user': getpass.getuser()
            }
        except Exception as e:
            logger.warning(f"SESSION_LOCK: Error getting process info: {e}")
            return {
                'name': 'unknown',
                'cmdline': ['unknown'],
                'user': 'unknown'
            }
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID"""
        import uuid
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"lifeboard_{timestamp}_{short_uuid}"
    
    async def get_session_status(self) -> Dict[str, Any]:
        """Get current session status"""
        status = {
            'has_current_session': self.current_session is not None,
            'current_session': None,
            'heartbeat_running': self.heartbeat_task is not None and not self.heartbeat_task.done(),
            'lock_files_exist': {
                'session_file': self.session_file.exists(),
                'lock_file': self.lock_file.exists()
            }
        }
        
        if self.current_session:
            status['current_session'] = self.current_session.to_dict()
        
        return status
    
    async def list_all_sessions(self) -> List[Dict[str, Any]]:
        """List all session lock files in the lock directory"""
        sessions = []
        
        try:
            for lock_file in self.lock_dir.glob("*.lock"):
                try:
                    session_file = lock_file.with_suffix('.json')
                    if session_file.exists():
                        with open(session_file, 'r') as f:
                            session_data = json.load(f)
                        
                        session = SessionInfo.from_dict(session_data)
                        validation = await self._validate_session(session)
                        
                        session_info = session.to_dict()
                        session_info['validation'] = validation
                        sessions.append(session_info)
                        
                except Exception as e:
                    logger.warning(f"SESSION_LOCK: Error reading session file {lock_file}: {e}")
                    
        except Exception as e:
            logger.error(f"SESSION_LOCK: Error listing sessions: {e}")
        
        return sessions