from typing import Dict, Any
from datetime import datetime
import logging

from sources.base import DataItem
from sources.limitless_processor import BaseProcessor

logger = logging.getLogger(__name__)


class AppleMusicProcessor(BaseProcessor):
    """Processor for Apple Music content with Apple Music-specific formatting"""

    def process(self, item: DataItem) -> DataItem:
        """Process Apple Music data item"""
        processed_item = item

        # Parse track description if available
        processed_item = self._parse_track_description(processed_item)

        # Enrich metadata with Apple Music-specific information
        processed_item = self._enrich_apple_music_metadata(processed_item)

        # Track processing
        if 'processing_history' not in processed_item.metadata:
            processed_item.metadata['processing_history'] = []

        processed_item.metadata['processing_history'].append({
            'processor': self.get_processor_name(),
            'timestamp': datetime.now().isoformat(),
            'changes': 'apple_music_content_processing'
        })

        return processed_item

    def _parse_track_description(self, item: DataItem) -> DataItem:
        """Parse Track Description field format: 'Artist - Title'"""
        track_description = item.metadata.get('track_description', '')

        if track_description and ' - ' in track_description:
            parts = track_description.split(' - ', 1)
            if len(parts) == 2:
                item.metadata['artist'] = parts[0].strip()
                item.metadata['title'] = parts[1].strip()

        return item

    def _enrich_apple_music_metadata(self, item: DataItem) -> DataItem:
        """Add Apple Music-specific metadata enrichment"""
        enriched_metadata = {}

        # Play metrics
        play_count = item.metadata.get('play_count', 0)
        skip_count = item.metadata.get('skip_count', 0)
        play_duration_ms = item.metadata.get('play_duration_ms', 0)
        media_duration_ms = item.metadata.get('media_duration_ms', 0)

        enriched_metadata['play_metrics'] = {
            'play_count': play_count,
            'skip_count': skip_count,
            'total_plays': play_count + skip_count,
            'skip_rate': skip_count / (play_count + skip_count) if (play_count + skip_count) > 0 else 0,
            'completion_rate': (play_duration_ms / media_duration_ms) if media_duration_ms > 0 else 0,
            'was_skipped': skip_count > 0,
            'was_completed': play_duration_ms >= media_duration_ms * 0.95 if media_duration_ms > 0 else False
        }

        # Source analysis
        source_type = item.metadata.get('source_type', 'UNKNOWN')
        enriched_metadata['source_analysis'] = {
            'source_type': source_type,
            'is_mobile': source_type in ['IPHONE', 'ANDROID'],
            'is_desktop': source_type == 'COMPUTER',
            'is_voice_assistant': source_type in ['AMAZON', 'ALEXA'],
            'is_unknown': source_type == 'UNKNOWN_DEVICE'
        }

        # End reason analysis
        end_reason = item.metadata.get('end_reason', '')
        enriched_metadata['playback_analysis'] = {
            'end_reason': end_reason,
            'completed_naturally': end_reason == 'NATURAL_END_OF_TRACK',
            'manually_paused': end_reason == 'PLAYBACK_MANUALLY_PAUSED',
            'user_skipped': end_reason in ['TRACK_SKIPPED_FORWARDS', 'MANUALLY_SELECTED_PLAYBACK_OF_A_DIFF_ITEM'],
            'playback_suspended': end_reason == 'PLAYBACK_SUSPENDED'
        }

        # Content categorization
        artist = item.metadata.get('artist', '')
        album = item.metadata.get('album', '')
        genre = item.metadata.get('genre', '')

        enriched_metadata['content_info'] = {
            'has_artist': bool(artist),
            'has_album': bool(album),
            'has_genre': bool(genre),
            'artist': artist,
            'album': album,
            'genre': genre
        }

        # Time-based metadata (if hours field is available)
        hours = item.metadata.get('hours')
        if hours is not None:
            try:
                hour_int = int(hours)
                enriched_metadata['time_analysis'] = {
                    'hour_of_day': hour_int,
                    'is_business_hours': 9 <= hour_int <= 17,
                    'is_night': hour_int >= 22 or hour_int <= 6,
                    'is_morning': 6 <= hour_int <= 12,
                    'is_afternoon': 12 <= hour_int <= 18,
                    'is_evening': 18 <= hour_int <= 22
                }
            except (ValueError, TypeError):
                logger.warning(f"[APPLE MUSIC] Invalid hours value for track {item.source_id}: {hours}")

        # Merge with existing metadata
        item.metadata.update(enriched_metadata)

        return item
