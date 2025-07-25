"""
JSON utility functions for safe parsing and serialization

This module provides reusable utilities for handling JSON metadata
across the application, eliminating duplicate parsing logic.
"""

import json
import logging
from typing import Any, Optional, Dict, Union

logger = logging.getLogger(__name__)


class JSONMetadataParser:
    """Utility class for safe JSON metadata parsing and serialization"""
    
    @staticmethod
    def parse_metadata(metadata_str: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        Safely parse JSON metadata string to dictionary
        
        Args:
            metadata_str: JSON string to parse, can be None
            
        Returns:
            Parsed dictionary or None if parsing fails or input is None
        """
        if not metadata_str:
            return None
        
        try:
            parsed = json.loads(metadata_str)
            # Ensure we return a dict, not other JSON types
            if isinstance(parsed, dict):
                return parsed
            else:
                logger.warning(f"Metadata is not a dictionary: {type(parsed)}")
                return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON metadata: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error parsing metadata: {e}")
            return None
    
    @staticmethod
    def serialize_metadata(metadata: Optional[Union[Dict[str, Any], str]]) -> Optional[str]:
        """
        Safely serialize metadata to JSON string
        
        Args:
            metadata: Dictionary to serialize or string to pass through
            
        Returns:
            JSON string or None if serialization fails
        """
        if metadata is None:
            return None
        
        # If already a string, return as-is
        if isinstance(metadata, str):
            return metadata
        
        try:
            return json.dumps(metadata)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize metadata: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error serializing metadata: {e}")
            return None
    
    @staticmethod
    def safe_get_value(data: Optional[Dict[str, Any]], key: str, default: Any = None) -> Any:
        """
        Safely get value from parsed metadata dictionary
        
        Args:
            data: Parsed metadata dictionary
            key: Key to retrieve
            default: Default value if key not found
            
        Returns:
            Value from dictionary or default
        """
        if not isinstance(data, dict):
            return default
        
        return data.get(key, default)
    
    @staticmethod
    def update_metadata(
        existing_metadata: Optional[str], 
        updates: Dict[str, Any]
    ) -> Optional[str]:
        """
        Update existing JSON metadata with new values
        
        Args:
            existing_metadata: Existing JSON metadata string
            updates: Dictionary of updates to apply
            
        Returns:
            Updated JSON metadata string
        """
        # Parse existing metadata
        parsed = JSONMetadataParser.parse_metadata(existing_metadata) or {}
        
        # Apply updates
        parsed.update(updates)
        
        # Serialize back to JSON
        return JSONMetadataParser.serialize_metadata(parsed)
    
    @staticmethod
    def merge_metadata(
        metadata1: Optional[str], 
        metadata2: Optional[str]
    ) -> Optional[str]:
        """
        Merge two JSON metadata strings
        
        Args:
            metadata1: First metadata string (base)
            metadata2: Second metadata string (updates)
            
        Returns:
            Merged JSON metadata string
        """
        parsed1 = JSONMetadataParser.parse_metadata(metadata1) or {}
        parsed2 = JSONMetadataParser.parse_metadata(metadata2) or {}
        
        # Merge with metadata2 taking precedence
        merged = {**parsed1, **parsed2}
        
        return JSONMetadataParser.serialize_metadata(merged)


class DatabaseRowParser:
    """Helper class for parsing database rows with metadata"""
    
    @staticmethod
    def parse_row_with_metadata(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse a database row and safely parse its metadata field
        
        Args:
            row: Database row as dictionary
            
        Returns:
            Row dictionary with parsed metadata
        """
        # Create a copy to avoid modifying the original
        parsed_row = dict(row)
        
        # Parse metadata field if present
        if 'metadata' in parsed_row:
            parsed_row['metadata'] = JSONMetadataParser.parse_metadata(
                parsed_row['metadata']
            )
        
        return parsed_row
    
    @staticmethod
    def parse_rows_with_metadata(rows: list) -> list:
        """
        Parse multiple database rows and safely parse their metadata fields
        
        Args:
            rows: List of database rows
            
        Returns:
            List of rows with parsed metadata
        """
        return [
            DatabaseRowParser.parse_row_with_metadata(row) 
            for row in rows
        ]