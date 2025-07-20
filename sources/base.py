from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from pydantic import BaseModel
from datetime import datetime
import logging


logger = logging.getLogger(__name__)


class DataItem(BaseModel):
    """Represents a single item of data from a source"""
    source_id: str  # Unique identifier within the source
    content: str    # Main text content
    metadata: Optional[Dict[str, Any]] = None  # Additional metadata
    timestamp: Optional[datetime] = None  # When the item was created/updated
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SourceSyncResult(BaseModel):
    """Result of a source synchronization operation"""
    source_namespace: str
    items_fetched: int
    items_added: int
    items_updated: int
    items_failed: int
    sync_duration_seconds: float
    last_sync_time: datetime
    errors: List[str] = []
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of the sync"""
        total = self.items_added + self.items_updated + self.items_failed
        if total == 0:
            return 1.0
        return (self.items_added + self.items_updated) / total


class SourceBase(ABC):
    """Abstract base class for all data sources"""
    
    def __init__(self, namespace: str, config: Dict[str, Any] = None):
        self.namespace = namespace
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def fetch_data(self, since: Optional[datetime] = None) -> AsyncGenerator[DataItem, None]:
        """
        Fetch data from this source
        
        Args:
            since: Only fetch data updated since this timestamp (for incremental sync)
            
        Yields:
            DataItem: Individual data items from the source
        """
        pass
    
    @abstractmethod
    async def get_source_info(self) -> Dict[str, Any]:
        """
        Get metadata about this source
        
        Returns:
            Dictionary containing source metadata like total items, last update time, etc.
        """
        pass
    
    async def validate_config(self) -> List[str]:
        """
        Validate the source configuration
        
        Returns:
            List of validation error messages (empty if valid)
        """
        return []
    
    async def test_connection(self) -> bool:
        """
        Test if the source is accessible and properly configured
        
        Returns:
            True if connection is successful, False otherwise
        """
        try:
            await self.get_source_info()
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def get_display_name(self) -> str:
        """Get human-readable name for this source"""
        return f"{self.__class__.__name__}({self.namespace})"
    
    def get_source_type(self) -> str:
        """Get the type identifier for this source"""
        return self.__class__.__name__.lower().replace('source', '')


class FileSource(SourceBase):
    """Source for reading data from files"""
    
    def __init__(self, namespace: str, config: Dict[str, Any]):
        super().__init__(namespace, config)
        self.file_path = config.get('file_path')
        self.file_type = config.get('file_type', 'text')
        self.encoding = config.get('encoding', 'utf-8')
    
    async def validate_config(self) -> List[str]:
        errors = []
        if not self.file_path:
            errors.append("file_path is required")
        elif not os.path.exists(self.file_path):
            errors.append(f"File not found: {self.file_path}")
        
        if self.file_type not in ['text', 'json', 'csv']:
            errors.append(f"Unsupported file_type: {self.file_type}")
        
        return errors
    
    async def fetch_data(self, since: Optional[datetime] = None) -> AsyncGenerator[DataItem, None]:
        """Read data from file"""
        import os
        import aiofiles
        
        if not await self.test_connection():
            return
        
        file_mtime = datetime.fromtimestamp(os.path.getmtime(self.file_path))
        
        # Skip if file hasn't been modified since last sync
        if since and file_mtime <= since:
            return
        
        try:
            async with aiofiles.open(self.file_path, 'r', encoding=self.encoding) as f:
                if self.file_type == 'text':
                    content = await f.read()
                    yield DataItem(
                        source_id=os.path.basename(self.file_path),
                        content=content,
                        timestamp=file_mtime,
                        metadata={
                            'file_path': self.file_path,
                            'file_size': os.path.getsize(self.file_path),
                            'file_type': self.file_type
                        }
                    )
                elif self.file_type == 'json':
                    import json
                    content = await f.read()
                    data = json.loads(content)
                    
                    if isinstance(data, list):
                        for i, item in enumerate(data):
                            yield DataItem(
                                source_id=f"{os.path.basename(self.file_path)}_{i}",
                                content=str(item),
                                timestamp=file_mtime,
                                metadata={'file_path': self.file_path, 'item_index': i}
                            )
                    else:
                        yield DataItem(
                            source_id=os.path.basename(self.file_path),
                            content=str(data),
                            timestamp=file_mtime,
                            metadata={'file_path': self.file_path}
                        )
                        
        except Exception as e:
            self.logger.error(f"Error reading file {self.file_path}: {e}")
            raise
    
    async def get_source_info(self) -> Dict[str, Any]:
        """Get file metadata"""
        import os
        
        if not os.path.exists(self.file_path):
            raise FileNotFoundError(f"File not found: {self.file_path}")
        
        stat = os.stat(self.file_path)
        return {
            'file_path': self.file_path,
            'file_size': stat.st_size,
            'last_modified': datetime.fromtimestamp(stat.st_mtime),
            'file_type': self.file_type,
            'encoding': self.encoding
        }


class APISource(SourceBase):
    """Base class for API-based sources"""
    
    def __init__(self, namespace: str, config: Dict[str, Any]):
        super().__init__(namespace, config)
        self.base_url = config.get('base_url')
        self.api_key = config.get('api_key')
        self.timeout = config.get('timeout', 30)
        self.headers = config.get('headers', {})
        
        if self.api_key:
            self.headers.update(self._get_auth_headers())
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers - override in subclasses"""
        return {'Authorization': f'Bearer {self.api_key}'}
    
    async def validate_config(self) -> List[str]:
        errors = []
        if not self.base_url:
            errors.append("base_url is required")
        if not self.api_key:
            errors.append("api_key is required")
        return errors
    
    async def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make HTTP request to API"""
        import aiohttp
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout)) as session:
            async with session.get(url, headers=self.headers, params=params) as response:
                response.raise_for_status()
                return await response.json()
    
    async def fetch_data(self, since: Optional[datetime] = None) -> AsyncGenerator[DataItem, None]:
        """Override in API-specific subclasses"""
        raise NotImplementedError("API subclasses must implement fetch_data")
    
    async def get_source_info(self) -> Dict[str, Any]:
        """Override in API-specific subclasses"""
        raise NotImplementedError("API subclasses must implement get_source_info")


class LimitlessSource(APISource):
    """Source for Limitless API data"""
    
    def __init__(self, namespace: str, config: Dict[str, Any]):
        super().__init__(namespace, config)
        self.timezone = config.get('timezone', 'UTC')
        self.include_markdown = config.get('include_markdown', True)
        self.include_headings = config.get('include_headings', True)
        self.page_limit = config.get('page_limit', 10)
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Limitless uses X-API-Key header"""
        return {'X-API-Key': self.api_key}
    
    async def fetch_data(self, since: Optional[datetime] = None) -> AsyncGenerator[DataItem, None]:
        """Fetch lifelogs from Limitless API"""
        params = {
            'timezone': self.timezone,
            'includeMarkdown': self.include_markdown,
            'includeHeadings': self.include_headings,
            'limit': self.page_limit,
            'direction': 'desc'
        }
        
        if since:
            params['start'] = since.isoformat()
        
        cursor = None
        
        try:
            while True:
                if cursor:
                    params['cursor'] = cursor
                
                response = await self._make_request('lifelogs', params)
                lifelogs = response.get('data', {}).get('lifelogs', [])
                
                if not lifelogs:
                    break
                
                for lifelog in lifelogs:
                    # Create main content from markdown or title
                    content = lifelog.get('markdown', lifelog.get('title', ''))
                    
                    # Add structured contents if available
                    if lifelog.get('contents'):
                        content_parts = [content] if content else []
                        for content_item in lifelog['contents']:
                            if content_item.get('content'):
                                content_parts.append(content_item['content'])
                        content = '\n\n'.join(content_parts)
                    
                    # Parse timestamps
                    start_time = None
                    end_time = None
                    try:
                        if lifelog.get('startTime'):
                            start_time = datetime.fromisoformat(lifelog['startTime'].replace('Z', '+00:00'))
                        if lifelog.get('endTime'):
                            end_time = datetime.fromisoformat(lifelog['endTime'].replace('Z', '+00:00'))
                    except ValueError as e:
                        self.logger.warning(f"Error parsing timestamp: {e}")
                    
                    yield DataItem(
                        source_id=lifelog['id'],
                        content=content,
                        timestamp=start_time or datetime.now(),
                        metadata={
                            'title': lifelog.get('title'),
                            'start_time': start_time.isoformat() if start_time else None,
                            'end_time': end_time.isoformat() if end_time else None,
                            'contents': lifelog.get('contents', []),
                            'source_type': 'limitless_lifelog'
                        }
                    )
                
                # Check for next page
                cursor = response.get('meta', {}).get('lifelogs', {}).get('nextCursor')
                if not cursor:
                    break
                    
        except Exception as e:
            self.logger.error(f"Error fetching Limitless data: {e}")
            raise
    
    async def get_source_info(self) -> Dict[str, Any]:
        """Get info about Limitless source"""
        try:
            # Make a small request to test connection and get basic info
            response = await self._make_request('lifelogs', {
                'limit': 1,
                'timezone': self.timezone
            })
            
            count = response.get('meta', {}).get('lifelogs', {}).get('count', 0)
            
            return {
                'source_type': 'limitless',
                'base_url': self.base_url,
                'timezone': self.timezone,
                'estimated_total_items': count,
                'include_markdown': self.include_markdown,
                'include_headings': self.include_headings
            }
            
        except Exception as e:
            self.logger.error(f"Error getting Limitless source info: {e}")
            raise


class DatabaseSource(SourceBase):
    """Source for reading data from databases"""
    
    def __init__(self, namespace: str, config: Dict[str, Any]):
        super().__init__(namespace, config)
        self.connection_string = config.get('connection_string')
        self.query = config.get('query')
        self.db_type = config.get('db_type', 'sqlite')
    
    async def validate_config(self) -> List[str]:
        errors = []
        if not self.connection_string:
            errors.append("connection_string is required")
        if not self.query:
            errors.append("query is required")
        return errors
    
    async def fetch_data(self, since: Optional[datetime] = None) -> AsyncGenerator[DataItem, None]:
        """Fetch data from database query"""
        # Implementation would depend on database type
        # This is a placeholder for future database integrations
        raise NotImplementedError("Database source not yet implemented")
    
    async def get_source_info(self) -> Dict[str, Any]:
        """Get database source info"""
        return {
            'source_type': 'database',
            'db_type': self.db_type,
            'connection_string': '***masked***'  # Don't expose credentials
        }