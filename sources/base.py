from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass
from datetime import datetime


@dataclass
class DataItem:
    """Standardized data item for ingestion"""
    namespace: str
    source_id: str
    content: str
    metadata: Dict[str, Any]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BaseSource(ABC):
    """Base class for all data sources"""
    
    def __init__(self, namespace: str, *args, **kwargs):
        self.namespace = namespace
        super().__init__(*args, **kwargs)
    
    @abstractmethod
    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100) -> AsyncIterator[DataItem]:
        """Fetch data items from the source"""
        pass
    
    @abstractmethod
    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """Get a specific item by source ID"""
        pass
    
    @abstractmethod
    def get_source_type(self) -> str:
        """Return the source type identifier"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the source is accessible"""
        pass
    
    async def get_sync_metadata(self) -> Dict[str, Any]:
        """Return metadata about the last sync"""
        return {}