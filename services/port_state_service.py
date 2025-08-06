"""
Port State Service for robust network binding management

This service provides comprehensive port and network state validation,
conflict detection, and recovery mechanisms for the Lifeboard application.
"""

import asyncio
import socket
import subprocess
import time
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

from core.logging_config import get_logger

logger = get_logger(__name__)


class PortState(Enum):
    """Port binding states"""
    AVAILABLE = "available"
    BOUND = "bound"
    LISTENING = "listening"
    CLOSED = "closed"
    CONFLICT = "conflict"
    UNKNOWN = "unknown"


class NetworkBindingStatus(Enum):
    """Network binding validation status"""
    SUCCESS = "success"
    BINDING_FAILED = "binding_failed"
    NOT_LISTENING = "not_listening"
    CONNECTION_REFUSED = "connection_refused"
    TIMEOUT = "timeout"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class PortValidationResult:
    """Result of port validation"""
    port: int
    host: str
    state: PortState
    binding_status: NetworkBindingStatus
    can_bind: bool
    can_connect: bool
    process_info: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    validation_time: datetime = None
    response_time_ms: Optional[float] = None

    def __post_init__(self):
        if self.validation_time is None:
            self.validation_time = datetime.now(timezone.utc)


@dataclass
class ProcessInfo:
    """Information about a process using a port"""
    pid: int
    command: str
    user: str
    process_name: str
    is_our_server: bool = False


class PortStateService:
    """Service for managing port states and network binding validation"""

    def __init__(self):
        self.validation_cache: Dict[str, PortValidationResult] = {}
        self.cache_ttl_seconds = 30  # Cache results for 30 seconds
        
        # Validation timeouts
        self.bind_timeout = 5.0
        self.connect_timeout = 3.0
        self.process_lookup_timeout = 10.0
        
        # Retry policies
        self.max_bind_retries = 3
        self.retry_delay_seconds = 1.0
        
    async def validate_port_binding(self, host: str, port: int, 
                                   validate_connectivity: bool = True) -> PortValidationResult:
        """
        Comprehensive port binding validation
        
        Args:
            host: Host address to validate
            port: Port number to validate  
            validate_connectivity: Whether to test actual connectivity
            
        Returns:
            PortValidationResult with comprehensive validation data
        """
        cache_key = f"{host}:{port}"
        
        # Check cache first
        if cache_key in self.validation_cache:
            cached_result = self.validation_cache[cache_key]
            age_seconds = (datetime.now(timezone.utc) - cached_result.validation_time).total_seconds()
            if age_seconds < self.cache_ttl_seconds:
                logger.debug(f"PORT_VALIDATION: Using cached result for {cache_key}")
                return cached_result
        
        logger.info(f"PORT_VALIDATION: Validating port binding for {host}:{port}")
        start_time = time.time()
        
        result = PortValidationResult(
            port=port,
            host=host,
            state=PortState.UNKNOWN,
            binding_status=NetworkBindingStatus.UNKNOWN_ERROR,
            can_bind=False,
            can_connect=False
        )
        
        try:
            # Step 1: Check if we can bind to the port
            bind_result = await self._test_port_binding(host, port)
            result.can_bind = bind_result['can_bind']
            result.binding_status = bind_result['status']
            result.error_message = bind_result.get('error')
            
            # Step 2: Determine port state
            if result.can_bind:
                result.state = PortState.AVAILABLE
            else:
                # Port is in use, get more details
                process_info = await self._get_port_process_info(port)
                result.process_info = process_info
                
                if process_info:
                    result.state = PortState.CONFLICT
                else:
                    result.state = PortState.BOUND
            
            # Step 3: Test connectivity if requested and port appears to be listening
            if validate_connectivity and not result.can_bind:
                connectivity_result = await self._test_port_connectivity(host, port)
                result.can_connect = connectivity_result['can_connect']
                result.response_time_ms = connectivity_result.get('response_time_ms')
                
                if result.can_connect:
                    result.state = PortState.LISTENING
                else:
                    # Port is bound but not accepting connections
                    result.state = PortState.CLOSED
                    if not result.error_message:
                        result.error_message = connectivity_result.get('error', 'Port bound but not responding')
            
            # Step 4: Update binding status based on final state
            if result.state == PortState.AVAILABLE:
                result.binding_status = NetworkBindingStatus.SUCCESS
            elif result.state == PortState.LISTENING:
                result.binding_status = NetworkBindingStatus.SUCCESS
            elif result.state == PortState.CLOSED:
                result.binding_status = NetworkBindingStatus.NOT_LISTENING
            elif result.state == PortState.CONFLICT:
                result.binding_status = NetworkBindingStatus.BINDING_FAILED
                
        except asyncio.TimeoutError:
            result.binding_status = NetworkBindingStatus.TIMEOUT
            result.error_message = f"Validation timed out after {self.bind_timeout}s"
        except Exception as e:
            logger.error(f"PORT_VALIDATION: Unexpected error validating {host}:{port}: {e}")
            result.binding_status = NetworkBindingStatus.UNKNOWN_ERROR
            result.error_message = str(e)
        
        # Record validation time
        validation_time = time.time() - start_time
        logger.info(f"PORT_VALIDATION: Completed validation for {host}:{port} in {validation_time:.3f}s - "
                   f"State: {result.state.value}, Status: {result.binding_status.value}")
        
        # Cache result
        self.validation_cache[cache_key] = result
        
        return result
    
    async def _test_port_binding(self, host: str, port: int) -> Dict[str, Any]:
        """Test if we can bind to a port"""
        for attempt in range(self.max_bind_retries):
            try:
                # Create socket with appropriate family
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.settimeout(self.bind_timeout)
                
                try:
                    sock.bind((host, port))
                    sock.close()
                    logger.debug(f"PORT_BIND: Successfully bound to {host}:{port} on attempt {attempt + 1}")
                    return {
                        'can_bind': True,
                        'status': NetworkBindingStatus.SUCCESS,
                        'attempt': attempt + 1
                    }
                except OSError as e:
                    sock.close()
                    if e.errno in [48, 98]:  # Address already in use
                        return {
                            'can_bind': False,
                            'status': NetworkBindingStatus.BINDING_FAILED,
                            'error': f"Address already in use (errno {e.errno})",
                            'errno': e.errno
                        }
                    elif e.errno == 13:  # Permission denied
                        return {
                            'can_bind': False, 
                            'status': NetworkBindingStatus.BINDING_FAILED,
                            'error': f"Permission denied for port {port}",
                            'errno': e.errno
                        }
                    else:
                        # Other errors might be transient, retry
                        if attempt < self.max_bind_retries - 1:
                            logger.debug(f"PORT_BIND: Bind attempt {attempt + 1} failed with errno {e.errno}, retrying...")
                            await asyncio.sleep(self.retry_delay_seconds)
                            continue
                        else:
                            return {
                                'can_bind': False,
                                'status': NetworkBindingStatus.BINDING_FAILED,
                                'error': f"Bind failed: {e} (errno {e.errno})",
                                'errno': e.errno
                            }
                        
            except asyncio.TimeoutError:
                return {
                    'can_bind': False,
                    'status': NetworkBindingStatus.TIMEOUT,
                    'error': f"Bind test timed out after {self.bind_timeout}s"
                }
            except Exception as e:
                if attempt < self.max_bind_retries - 1:
                    logger.debug(f"PORT_BIND: Unexpected error on attempt {attempt + 1}: {e}, retrying...")
                    await asyncio.sleep(self.retry_delay_seconds)
                    continue
                else:
                    return {
                        'can_bind': False,
                        'status': NetworkBindingStatus.UNKNOWN_ERROR,
                        'error': f"Unexpected bind test error: {e}"
                    }
        
        # Should not reach here
        return {
            'can_bind': False,
            'status': NetworkBindingStatus.UNKNOWN_ERROR,
            'error': "All bind attempts exhausted"
        }
    
    async def _test_port_connectivity(self, host: str, port: int) -> Dict[str, Any]:
        """Test if we can connect to a port"""
        start_time = time.time()
        
        try:
            # Create connection with timeout
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connect_timeout)
            
            try:
                result = sock.connect_ex((host, port))
                response_time_ms = (time.time() - start_time) * 1000
                
                if result == 0:
                    sock.close()
                    logger.debug(f"PORT_CONNECT: Successfully connected to {host}:{port} in {response_time_ms:.1f}ms")
                    return {
                        'can_connect': True,
                        'response_time_ms': response_time_ms
                    }
                else:
                    sock.close()
                    return {
                        'can_connect': False,
                        'error': f"Connection refused (error code {result})",
                        'error_code': result
                    }
                    
            except socket.timeout:
                sock.close()
                return {
                    'can_connect': False,
                    'error': f"Connection timed out after {self.connect_timeout}s"
                }
            except OSError as e:
                sock.close()
                return {
                    'can_connect': False,
                    'error': f"Connection failed: {e}",
                    'errno': e.errno
                }
                
        except Exception as e:
            return {
                'can_connect': False,
                'error': f"Unexpected connectivity test error: {e}"
            }
    
    async def _get_port_process_info(self, port: int) -> Optional[Dict[str, Any]]:
        """Get information about processes using a port"""
        try:
            # Try lsof first (most reliable)
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    'lsof', '-i', f':{port}', '-P', '-n',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=self.process_lookup_timeout
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0 and stdout:
                return self._parse_lsof_output(stdout.decode(), port)
            else:
                # Fallback to netstat
                return await self._get_process_info_netstat(port)
                
        except asyncio.TimeoutError:
            logger.warning(f"PORT_PROCESS: Process lookup timed out for port {port}")
            return None
        except FileNotFoundError:
            # lsof not available, try netstat
            return await self._get_process_info_netstat(port)
        except Exception as e:
            logger.warning(f"PORT_PROCESS: Error getting process info for port {port}: {e}")
            return None
    
    def _parse_lsof_output(self, output: str, port: int) -> Optional[Dict[str, Any]]:
        """Parse lsof output to extract process information"""
        try:
            lines = output.strip().split('\n')
            if len(lines) < 2:  # Header + at least one process line
                return None
            
            # Skip header line, process the first process entry
            process_line = lines[1]
            parts = process_line.split()
            
            if len(parts) < 8:
                return None
            
            command = parts[0]
            pid = int(parts[1]) 
            user = parts[2]
            
            # Check if this might be our server process
            is_our_server = (
                'python' in command.lower() or
                'uvicorn' in command.lower() or
                'server.py' in command.lower()
            )
            
            return {
                'pid': pid,
                'command': command,
                'user': user,
                'process_name': command,
                'is_our_server': is_our_server,
                'port': port,
                'source': 'lsof'
            }
            
        except (ValueError, IndexError) as e:
            logger.warning(f"PORT_PROCESS: Failed to parse lsof output: {e}")
            return None
    
    async def _get_process_info_netstat(self, port: int) -> Optional[Dict[str, Any]]:
        """Fallback method using netstat to get process info"""
        try:
            # Try netstat with process info
            result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    'netstat', '-tulpn',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                ),
                timeout=self.process_lookup_timeout
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0 and stdout:
                return self._parse_netstat_output(stdout.decode(), port)
            
        except (asyncio.TimeoutError, FileNotFoundError, Exception) as e:
            logger.debug(f"PORT_PROCESS: Netstat fallback failed for port {port}: {e}")
        
        return None
    
    def _parse_netstat_output(self, output: str, port: int) -> Optional[Dict[str, Any]]:
        """Parse netstat output to extract process information"""
        try:
            for line in output.split('\n'):
                if f':{port} ' in line or f':{port}\t' in line:
                    parts = line.split()
                    if len(parts) >= 7:
                        # Extract PID/Program from last column
                        pid_program = parts[-1]
                        if '/' in pid_program:
                            pid_str, program = pid_program.split('/', 1)
                            try:
                                pid = int(pid_str)
                                
                                is_our_server = (
                                    'python' in program.lower() or
                                    'uvicorn' in program.lower()
                                )
                                
                                return {
                                    'pid': pid,
                                    'command': program,
                                    'user': 'unknown',
                                    'process_name': program,
                                    'is_our_server': is_our_server,
                                    'port': port,
                                    'source': 'netstat'
                                }
                            except ValueError:
                                pass
            
        except Exception as e:
            logger.warning(f"PORT_PROCESS: Failed to parse netstat output: {e}")
        
        return None
    
    async def find_available_port(self, start_port: int, host: str = "0.0.0.0", 
                                 max_attempts: int = 100) -> Optional[int]:
        """
        Find an available port starting from start_port
        
        Args:
            start_port: Port to start searching from
            host: Host to test binding on
            max_attempts: Maximum number of ports to try
            
        Returns:
            Available port number or None if none found
        """
        logger.info(f"PORT_SEARCH: Looking for available port starting from {start_port}")
        
        for port in range(start_port, start_port + max_attempts):
            result = await self.validate_port_binding(host, port, validate_connectivity=False)
            
            if result.state == PortState.AVAILABLE:
                logger.info(f"PORT_SEARCH: Found available port: {port}")
                return port
            
            logger.debug(f"PORT_SEARCH: Port {port} not available - {result.state.value}")
        
        logger.error(f"PORT_SEARCH: No available ports found in range {start_port}-{start_port + max_attempts - 1}")
        return None
    
    async def validate_server_binding(self, host: str, port: int) -> Dict[str, Any]:
        """
        Validate that a server is properly bound and listening
        
        This is the main method for post-startup validation
        """
        logger.info(f"SERVER_VALIDATION: Validating server binding for {host}:{port}")
        
        validation_result = await self.validate_port_binding(host, port, validate_connectivity=True)
        
        validation_summary = {
            'is_healthy': False,
            'port': port,
            'host': host,
            'state': validation_result.state.value,
            'binding_status': validation_result.binding_status.value,
            'can_bind': validation_result.can_bind,
            'can_connect': validation_result.can_connect,
            'response_time_ms': validation_result.response_time_ms,
            'issues': [],
            'recommendations': [],
            'validation_time': validation_result.validation_time.isoformat()
        }
        
        # Analyze results and provide recommendations
        if validation_result.state == PortState.LISTENING and validation_result.can_connect:
            validation_summary['is_healthy'] = True
            logger.info(f"SERVER_VALIDATION: Server binding is healthy for {host}:{port}")
            
        elif validation_result.state == PortState.CLOSED:
            validation_summary['issues'].append({
                'type': 'port_not_listening',
                'severity': 'critical', 
                'message': f'Port {port} is bound but not accepting connections',
                'details': validation_result.error_message
            })
            validation_summary['recommendations'].append({
                'action': 'restart_server',
                'description': 'Server process may be hung or misconfigured'
            })
            
        elif validation_result.state == PortState.CONFLICT:
            process_info = validation_result.process_info
            if process_info and process_info.get('is_our_server'):
                validation_summary['issues'].append({
                    'type': 'existing_server_instance',
                    'severity': 'warning',
                    'message': f'Another server instance is using port {port}',
                    'details': process_info
                })
                validation_summary['recommendations'].append({
                    'action': 'kill_existing_process',
                    'description': f'Terminate existing server process (PID: {process_info.get("pid")})'
                })
            else:
                validation_summary['issues'].append({
                    'type': 'port_conflict',
                    'severity': 'critical',
                    'message': f'Port {port} is used by another application',
                    'details': process_info
                })
                validation_summary['recommendations'].append({
                    'action': 'use_different_port',
                    'description': 'Use a different port or stop the conflicting application'
                })
                
        elif validation_result.state == PortState.AVAILABLE:
            validation_summary['issues'].append({
                'type': 'server_not_running',
                'severity': 'critical',
                'message': f'No server process bound to port {port}',
                'details': 'Server may have failed to start or crashed'
            })
            validation_summary['recommendations'].append({
                'action': 'start_server',
                'description': 'Start the server process'
            })
        
        return validation_summary
    
    def clear_cache(self):
        """Clear the validation cache"""
        self.validation_cache.clear()
        logger.debug("PORT_VALIDATION: Cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        now = datetime.now(timezone.utc)
        valid_entries = 0
        expired_entries = 0
        
        for result in self.validation_cache.values():
            age_seconds = (now - result.validation_time).total_seconds()
            if age_seconds < self.cache_ttl_seconds:
                valid_entries += 1
            else:
                expired_entries += 1
        
        return {
            'total_entries': len(self.validation_cache),
            'valid_entries': valid_entries,
            'expired_entries': expired_entries,
            'cache_ttl_seconds': self.cache_ttl_seconds
        }