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
    def _is_valid_iso_timestamp(timestamp_str: str) -> bool:
        """
        Check if a string is a valid ISO timestamp format
        
        Args:
            timestamp_str: String to check
            
        Returns:
            True if it looks like a valid ISO timestamp
        """
        try:
            # Basic format check for ISO timestamp patterns
            if not timestamp_str or len(timestamp_str) < 10:
                return False
            
            # Check for common ISO timestamp patterns
            import re
            iso_pattern = r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?$'
            if re.match(iso_pattern, timestamp_str):
                # Try to actually parse it to be sure
                from datetime import datetime
                datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                return True
        except (ValueError, TypeError, ImportError):
            pass
        return False
    
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
        
        # Handle edge case where metadata might already be a dict
        if isinstance(metadata_str, dict):
            return metadata_str
        
        try:
            # Clean up common issues with JSON strings
            cleaned_str = metadata_str.strip()
            
            # Check for double-serialization (JSON string containing escaped JSON)
            if cleaned_str.startswith('"') and cleaned_str.endswith('"'):
                try:
                    # First, try to parse as a string that contains JSON
                    unescaped = json.loads(cleaned_str)
                    if isinstance(unescaped, str):
                        # Only use the unescaped version if it looks like JSON
                        # (starts with { or [ indicating actual double-serialization)
                        if unescaped.strip().startswith(('{', '[')):
                            cleaned_str = unescaped
                except (json.JSONDecodeError, TypeError):
                    # If that fails, use the original cleaned string
                    pass
            
            parsed = json.loads(cleaned_str)
            # Return the parsed JSON value (dict, string, number, etc.)
            return parsed
        except json.JSONDecodeError as e:
            # DEFENSIVE FIX: Handle raw strings that aren't valid JSON
            # Common case: raw timestamp strings like "2025-07-31T02:51:57.519"
            # being passed instead of proper JSON
            
            # Check if this is a valid ISO timestamp before wrapping
            if JSONMetadataParser._is_valid_iso_timestamp(cleaned_str):
                logger.debug(f"Detected valid ISO timestamp string, returning as-is: {cleaned_str}")
                return cleaned_str
            
            if "Extra data" in str(e) and e.pos == 4:
                # This is likely a raw string being passed to the JSON parser
                # Return the string as-is, wrapped in a simple structure
                logger.info(f"Converting raw string to JSON-compatible format: {metadata_str[:50]}...")
                return {"raw_value": metadata_str}
            
            # For other JSON errors, provide helpful context
            error_pos = getattr(e, 'pos', 0)
            context_start = max(0, error_pos - 20)
            context_end = min(len(metadata_str), error_pos + 20)
            context = metadata_str[context_start:context_end]
            logger.warning(f"Failed to parse JSON metadata at position {error_pos}: {e}. Context: '...{context}...'")
            
            # Try to detect if this is a raw string and handle it gracefully
            if not cleaned_str.startswith(('{', '[', '"')) and not cleaned_str.endswith(('}', ']', '"')):
                # Check again if this looks like a timestamp before wrapping
                if JSONMetadataParser._is_valid_iso_timestamp(cleaned_str):
                    logger.debug(f"Detected valid ISO timestamp, returning as string: {cleaned_str}")
                    return cleaned_str
                
                # This looks like a raw string, wrap it properly
                logger.info(f"Detected raw string input, wrapping as JSON-compatible: {cleaned_str[:50]}...")
                return {"raw_value": cleaned_str}
            
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
        
        # If already a string, validate it's proper JSON before returning
        if isinstance(metadata, str):
            try:
                # Validate that it's proper JSON
                json.loads(metadata)
                return metadata
            except json.JSONDecodeError:
                logger.warning(f"Metadata string is not valid JSON, attempting to fix. Malformed JSON: {metadata}")
                # If it's not valid JSON, treat it as a raw string and serialize it
                return json.dumps(metadata)
        
        try:
            return json.dumps(metadata, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize metadata: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error serializing metadata: {e}")
            return None
    
    @staticmethod
    def safe_get_value(data: Optional[Any], key: str, default: Any = None) -> Any:
        """
        Safely get value from parsed metadata dictionary
        
        Args:
            data: Parsed metadata (should be a dictionary)
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