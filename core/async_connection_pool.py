"""
Advanced Connection Pool Management for AsyncDatabaseService

Enterprise-grade async connection pooling with health monitoring,
dynamic sizing, and comprehensive statistics collection.

Implementation for Phase 8 enterprise architecture patterns.
"""

import asyncio
import aiosqlite
import time
import uuid
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta


class ConnectionPoolError(Exception):
    """Base exception for connection pool errors"""
    pass


class ConnectionHealthError(Exception):
    """Exception for connection health validation failures"""
    pass


@dataclass
class PoolStatistics:
    """Comprehensive connection pool statistics"""
    total_acquisitions: int = 0
    total_releases: int = 0
    current_active_connections: int = 0
    average_acquisition_time: float = 0.0
    max_concurrent_connections: int = 0
    health_check_passes: int = 0
    health_check_failures: int = 0
    acquisition_times: List[float] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    
    async def record_acquisition(self, duration: float):
        """Record connection acquisition metrics"""
        self.total_acquisitions += 1
        self.acquisition_times.append(duration)
        self.average_acquisition_time = sum(self.acquisition_times) / len(self.acquisition_times)
    
    async def record_release(self):
        """Record connection release"""
        self.total_releases += 1
        self.current_active_connections = max(0, self.current_active_connections - 1)
    
    async def record_health_check(self, success: bool):
        """Record health check result"""
        if success:
            self.health_check_passes += 1
        else:
            self.health_check_failures += 1
    
    @property
    def success_rate(self) -> float:
        """Calculate health check success rate"""
        total_checks = self.health_check_passes + self.health_check_failures
        if total_checks == 0:
            return 0.0
        return self.health_check_passes / total_checks


class AsyncHealthChecker:
    """Async health checker with configurable monitoring"""
    
    def __init__(self, interval: float = 30.0, timeout: float = 5.0):
        self.interval = interval
        self.timeout = timeout
        self.is_running = False
        self._callback: Optional[Callable] = None
        self._task: Optional[asyncio.Task] = None
        self._logger = logging.getLogger(__name__)
    
    def set_callback(self, callback: Callable):
        """Set health check callback function"""
        self._callback = callback
    
    async def start(self):
        """Start periodic health checking"""
        if self.is_running:
            return
        
        self.is_running = True
        self._task = asyncio.create_task(self._health_check_loop())
    
    async def stop(self):
        """Stop health checking"""
        if not self.is_running:
            return
        
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    async def _health_check_loop(self):
        """Main health check loop"""
        while self.is_running:
            try:
                if self._callback:
                    try:
                        await asyncio.wait_for(self._callback(), timeout=self.timeout)
                    except Exception as e:
                        self._logger.warning(f"Health check callback failed: {e}")
                
                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(1)


class AsyncDatabasePool:
    """Enterprise connection pool with health monitoring and dynamic sizing"""
    
    def __init__(self, 
                 db_path: str,
                 min_connections: int = 5,
                 max_connections: int = 20,
                 connection_timeout: float = 5.0,
                 health_check_interval: float = 30.0,
                 scale_up_threshold: float = 0.8,
                 scale_down_threshold: float = 0.2):
        self.db_path = db_path
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        
        # Connection management
        self._semaphore = asyncio.Semaphore(max_connections)
        self._connection_queue = asyncio.Queue(maxsize=max_connections)
        self._active_connections = set()
        self._all_connections = set()
        self.is_initialized = False
        
        # Health monitoring
        self._health_checker = AsyncHealthChecker(interval=health_check_interval)
        self._health_checker.set_callback(self._pool_health_check)
        
        # Statistics
        self.statistics = PoolStatistics()
        self._logger = logging.getLogger(__name__)
    
    @property
    def current_size(self) -> int:
        """Current total pool size"""
        return len(self._all_connections)
    
    @property
    def available_connections(self) -> int:
        """Currently available connections"""
        return self._connection_queue.qsize()
    
    async def initialize_pool(self):
        """Initialize connection pool with minimum connections"""
        if self.is_initialized:
            return
        
        self._logger.info(f"Initializing connection pool: min={self.min_connections}, max={self.max_connections}")
        
        # Create minimum connections
        for i in range(self.min_connections):
            try:
                conn = await aiosqlite.connect(self.db_path)
                conn.row_factory = aiosqlite.Row
                self._all_connections.add(conn)
                await self._connection_queue.put(conn)
                self._logger.debug(f"Created connection {i+1}/{self.min_connections}")
            except Exception as e:
                self._logger.error(f"Failed to create connection {i+1}: {e}")
                raise ConnectionPoolError(f"Failed to initialize pool: {e}")
        
        # Start health monitoring
        await self._health_checker.start()
        
        self.is_initialized = True
        self._logger.info(f"Connection pool initialized with {self.current_size} connections")
    
    @asynccontextmanager
    async def acquire_connection(self):
        """Acquire connection with timeout and health validation"""
        if not self.is_initialized:
            raise ConnectionPoolError("Pool not initialized")
        
        acquisition_start = time.perf_counter()
        
        async with self._semaphore:
            try:
                # Try to get connection from pool
                conn = await asyncio.wait_for(
                    self._connection_queue.get(), 
                    timeout=self.connection_timeout
                )
                
                # Validate connection health
                if not await self._validate_connection(conn):
                    self._logger.warning("Unhealthy connection detected, creating new one")
                    try:
                        await conn.close()
                    except:
                        pass
                    self._all_connections.discard(conn)
                    conn = await self._create_new_connection()
                
                # Track active connection
                self._active_connections.add(conn)
                self.statistics.current_active_connections = len(self._active_connections)
                self.statistics.max_concurrent_connections = max(
                    self.statistics.max_concurrent_connections,
                    self.statistics.current_active_connections
                )
                
                # Record acquisition time
                acquisition_time = time.perf_counter() - acquisition_start
                await self.statistics.record_acquisition(acquisition_time)
                
                yield conn
                
            finally:
                # Return connection to pool
                await self._return_connection(conn)
    
    async def _validate_connection(self, conn) -> bool:
        """Validate connection health"""
        try:
            await conn.execute("SELECT 1")
            await self.statistics.record_health_check(success=True)
            return True
        except Exception:
            await self.statistics.record_health_check(success=False)
            return False
    
    async def _create_new_connection(self):
        """Create new database connection"""
        try:
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            self._all_connections.add(conn)
            return conn
        except Exception as e:
            raise ConnectionPoolError(f"Failed to create new connection: {e}")
    
    async def _return_connection(self, conn):
        """Return connection to pool"""
        try:
            # Remove from active tracking
            self._active_connections.discard(conn)
            await self.statistics.record_release()
            
            # Validate before returning to pool
            if await self._validate_connection(conn) and self.is_initialized:
                try:
                    self._connection_queue.put_nowait(conn)
                except asyncio.QueueFull:
                    # Pool is full, close excess connection
                    await conn.close()
                    self._all_connections.discard(conn)
            else:
                # Connection unhealthy, close it
                try:
                    await conn.close()
                except:
                    pass
                self._all_connections.discard(conn)
        except Exception as e:
            self._logger.error(f"Error returning connection: {e}")
    
    async def _pool_health_check(self) -> Dict[str, Any]:
        """Perform pool health check"""
        return {
            "status": "healthy",
            "connections": {
                "total": self.current_size,
                "available": self.available_connections,
                "active": len(self._active_connections)
            },
            "statistics": {
                "total_acquisitions": self.statistics.total_acquisitions,
                "success_rate": self.statistics.success_rate
            }
        }
    
    async def _evaluate_scaling(self):
        """Evaluate if pool should scale up or down"""
        if not self.is_initialized:
            return
        
        utilization = len(self._active_connections) / self.current_size if self.current_size > 0 else 0
        
        # Scale up if utilization high and under max
        if (utilization > self.scale_up_threshold and 
            self.current_size < self.max_connections):
            try:
                conn = await self._create_new_connection()
                await self._connection_queue.put(conn)
                self._logger.info(f"Scaled up pool to {self.current_size} connections")
            except Exception as e:
                self._logger.error(f"Failed to scale up pool: {e}")
        
        # Scale down if utilization low and above min
        elif (utilization < self.scale_down_threshold and 
              self.current_size > self.min_connections and
              self.available_connections > 1):
            try:
                conn = await asyncio.wait_for(self._connection_queue.get(), timeout=0.1)
                await conn.close()
                self._all_connections.discard(conn)
                self._logger.info(f"Scaled down pool to {self.current_size} connections")
            except (asyncio.TimeoutError, Exception):
                pass  # No connections available for scaling down
    
    async def get_statistics(self) -> PoolStatistics:
        """Get current pool statistics"""
        return self.statistics
    
    async def close_pool(self, force: bool = False, timeout: float = 30.0):
        """Gracefully close all pool connections"""
        self._logger.info(f"Closing connection pool (force={force}, timeout={timeout})")
        
        # Stop health checking
        await self._health_checker.stop()
        
        if not force:
            # Wait for active connections to be released
            wait_start = time.perf_counter()
            while self._active_connections and (time.perf_counter() - wait_start) < timeout:
                await asyncio.sleep(0.1)
        
        # Close all connections
        all_connections = list(self._all_connections)
        for conn in all_connections:
            try:
                await conn.close()
            except Exception as e:
                self._logger.warning(f"Error closing connection: {e}")
        
        # Clear tracking
        self._all_connections.clear()
        self._active_connections.clear()
        
        # Clear queue
        while not self._connection_queue.empty():
            try:
                conn = self._connection_queue.get_nowait()
                await conn.close()
            except (asyncio.QueueEmpty, Exception):
                break
        
        self.is_initialized = False
        self._logger.info(f"Connection pool closed. Processed {len(all_connections)} connections")