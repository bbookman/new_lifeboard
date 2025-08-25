from typing import Dict, Any
from datetime import datetime
import json
import logging

from sources.base import DataItem
from sources.limitless_processor import BaseProcessor

logger = logging.getLogger(__name__)


class TwitterProcessor(BaseProcessor):
    """Processor for Twitter content with Twitter-specific formatting"""
    
    def process(self, item: DataItem) -> DataItem:
        """Process Twitter data item"""
        processed_item = item
        
        # Clean up Twitter content
        processed_item = self._clean_twitter_content(processed_item)
        
        # Enrich metadata with Twitter-specific information
        processed_item = self._enrich_twitter_metadata(processed_item)
        
        # Track processing
        if 'processing_history' not in processed_item.metadata:
            processed_item.metadata['processing_history'] = []
        
        processed_item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': 'twitter_content_processing'
        })
        
        return processed_item
    
    def _clean_twitter_content(self, item: DataItem) -> DataItem:
        """Clean and format Twitter content"""
        if not item.content:
            return item
        
        content = item.content
        
        # Remove common Twitter artifacts
        # Remove "RT @username:" retweet prefixes for cleaner search
        import re
        content = re.sub(r'^RT @\w+:\s*', '', content)
        
        # Clean up excessive newlines but preserve paragraph structure
        content = re.sub(r'\n{3,}', '\n\n', content)
        
        # Strip leading/trailing whitespace
        content = content.strip()
        
        item.content = content
        return item
    
    def _enrich_twitter_metadata(self, item: DataItem) -> DataItem:
        """Add Twitter-specific metadata enrichment"""
        enriched_metadata = {}
        
        # Basic content stats
        content = item.content or ""
        enriched_metadata['content_stats'] = {
            'character_count': len(content),
            'word_count': len(content.split()) if content else 0,
            'is_retweet': content.startswith('RT @') if content else False,
            'has_mentions': '@' in content if content else False,
            'has_hashtags': '#' in content if content else False,
            'has_urls': 'http' in content if content else False
        }
        
        # Parse media URLs if available
        media_urls = item.metadata.get('media_urls')
        if media_urls:
            try:
                if isinstance(media_urls, str):
                    media_list = json.loads(media_urls)
                else:
                    media_list = media_urls
                
                enriched_metadata['media'] = {
                    'has_media': len(media_list) > 0,
                    'media_count': len(media_list),
                    'media_urls': media_list
                }
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"[TWITTER IMPORT] Failed to parse media URLs for tweet {item.source_id}")
                enriched_metadata['media'] = {
                    'has_media': False,
                    'media_count': 0,
                    'media_urls': []
                }
        else:
            enriched_metadata['media'] = {
                'has_media': False,
                'media_count': 0,
                'media_urls': []
            }
        
        # Time-based metadata
        if item.created_at:
            enriched_metadata['time_analysis'] = {
                'hour_of_day': item.created_at.hour,
                'day_of_week': item.created_at.weekday(),  # 0=Monday, 6=Sunday
                'is_business_hours': 9 <= item.created_at.hour <= 17,
                'is_weekend': item.created_at.weekday() >= 5,
                'is_night': item.created_at.hour >= 22 or item.created_at.hour <= 6,
                'is_morning': 6 <= item.created_at.hour <= 12,
                'is_afternoon': 12 <= item.created_at.hour <= 18,
                'is_evening': 18 <= item.created_at.hour <= 22
            }
        
        # Merge with existing metadata
        item.metadata.update(enriched_metadata)
        
        return item