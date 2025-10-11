import csv
import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path
import tempfile

from config.models import AppleMusicConfig
from core.database import DatabaseService
from sources.base import BaseSource, DataItem
from sources.apple_music_processor import AppleMusicProcessor

logger = logging.getLogger(__name__)


class AppleMusicSource(BaseSource):
    """Apple Music data source for processing Apple Music archive files"""

    def __init__(self, config: AppleMusicConfig, db_service: DatabaseService = None):
        super().__init__("apple_music")
        self.config = config
        self.processor = AppleMusicProcessor()
        self.db_service = db_service or DatabaseService()

    async def process_directory(self, uploaded_files: List[tuple]) -> Dict[str, Any]:
        """
        Process Apple Music data from uploaded directory files.

        Args:
            uploaded_files: List of (filename, file_content_bytes) tuples

        Returns:
            Dict with success, imported_count, message, and data_items
        """
        if not self.config.is_configured():
            logger.warning("[APPLE MUSIC] Apple Music source not enabled. Skipping import.")
            return {
                "success": False,
                "imported_count": 0,
                "message": "Apple Music source is not enabled in the configuration."
            }

        try:
            logger.info(f"[APPLE MUSIC] Starting Apple Music import from {len(uploaded_files)} files")

            # Find required files
            play_history_content = None
            identifier_info_content = None
            library_tracks_content = None

            for filename, content_bytes in uploaded_files:
                filename_lower = filename.lower()
                if 'play history daily tracks.csv' in filename_lower:
                    play_history_content = content_bytes.decode('utf-8')
                    logger.info(f"[APPLE MUSIC] Found Play History Daily Tracks file: {filename}")
                elif 'identifier information.json' in filename_lower:
                    identifier_info_content = content_bytes.decode('utf-8')
                    logger.info(f"[APPLE MUSIC] Found Identifier Information file: {filename}")
                elif 'library tracks.json' in filename_lower:
                    library_tracks_content = content_bytes.decode('utf-8')
                    logger.info(f"[APPLE MUSIC] Found Library Tracks file: {filename}")

            # Validate required files
            if not play_history_content:
                logger.error("[APPLE MUSIC] Required file 'Apple Music - Play History Daily Tracks.csv' not found")
                return {
                    "success": False,
                    "imported_count": 0,
                    "message": "Required file 'Apple Music - Play History Daily Tracks.csv' not found in directory"
                }

            # Parse files
            logger.info("[APPLE MUSIC] Parsing Apple Music files...")

            # Parse identifier information if available
            identifier_map = {}
            if identifier_info_content:
                try:
                    identifier_data = json.loads(identifier_info_content)
                    for item in identifier_data:
                        identifier = item.get('Identifier')
                        title = item.get('Title')
                        if identifier and title:
                            identifier_map[identifier] = title
                    logger.info(f"[APPLE MUSIC] Loaded {len(identifier_map)} identifier mappings")
                except json.JSONDecodeError as e:
                    logger.warning(f"[APPLE MUSIC] Failed to parse Identifier Information: {e}")

            # Parse library tracks if available
            library_tracks_map = {}
            if library_tracks_content:
                try:
                    library_data = json.loads(library_tracks_content)
                    for item in library_data:
                        track_id = item.get('Track Identifier')
                        if track_id:
                            library_tracks_map[track_id] = item
                    logger.info(f"[APPLE MUSIC] Loaded {len(library_tracks_map)} library track records")
                except json.JSONDecodeError as e:
                    logger.warning(f"[APPLE MUSIC] Failed to parse Library Tracks: {e}")

            # Parse play history CSV
            parsed_tracks = self._parse_play_history_csv(
                play_history_content,
                identifier_map,
                library_tracks_map
            )
            logger.info(f"[APPLE MUSIC] Parsed {len(parsed_tracks)} tracks from Play History")

            if not parsed_tracks:
                return {
                    "success": True,
                    "imported_count": 0,
                    "message": "No tracks found in Play History file"
                }

            # Get existing track plays from database
            existing_source_ids = await self._get_existing_source_ids()
            logger.info(f"[APPLE MUSIC] Found {len(existing_source_ids)} existing track plays in database")

            # Filter out existing track plays
            new_tracks = [t for t in parsed_tracks if t['source_id'] not in existing_source_ids]
            logger.info(f"[APPLE MUSIC] Found {len(new_tracks)} new track plays to import")

            if not new_tracks:
                return {
                    "success": True,
                    "imported_count": 0,
                    "message": "Apple Music archive processed. No new track plays found to import."
                }

            # Transform tracks to DataItems
            data_items = self._transform_tracks_to_items(new_tracks)
            logger.info(f"[APPLE MUSIC] Transformed {len(data_items)} tracks to DataItems")

            return {
                "success": True,
                "imported_count": len(new_tracks),
                "message": f"Successfully imported {len(new_tracks)} new track plays from Apple Music.",
                "data_items": data_items
            }

        except Exception as e:
            logger.error(f"[APPLE MUSIC] Error processing Apple Music directory: {e}", exc_info=True)
            return {
                "success": False,
                "imported_count": 0,
                "message": f"An error occurred during import: {e}"
            }

    def _parse_play_history_csv(
        self,
        csv_content: str,
        identifier_map: Dict[str, str],
        library_tracks_map: Dict[str, Dict]
    ) -> List[Dict[str, Any]]:
        """Parse the Play History Daily Tracks CSV file"""
        parsed_tracks = []

        # Parse CSV
        csv_reader = csv.DictReader(csv_content.splitlines())

        for row in csv_reader:
            track_identifier = row.get('Track Identifier', '')
            date_played = row.get('Date Played', '')
            hours = row.get('Hours', '')

            if not track_identifier or not date_played:
                continue

            # Convert date format YYYYMMDD -> YYYY-MM-DD
            try:
                days_date = datetime.strptime(date_played, '%Y%m%d').strftime('%Y-%m-%d')
            except (ValueError, TypeError):
                logger.warning(f"[APPLE MUSIC] Could not parse date: {date_played}")
                continue

            # Create unique source_id: track_identifier:date_played:hours
            source_id = f"{track_identifier}:{date_played}:{hours}"

            # Get track description and parse it
            track_description = row.get('Track Description', '')
            artist = ''
            title = ''
            if track_description and ' - ' in track_description:
                parts = track_description.split(' - ', 1)
                if len(parts) == 2:
                    artist = parts[0].strip()
                    title = parts[1].strip()

            # Try to get title from identifier map if not available
            if not title and track_identifier in identifier_map:
                title = identifier_map[track_identifier]

            # Get additional metadata from library tracks
            album = ''
            genre = ''
            if track_identifier in library_tracks_map:
                library_track = library_tracks_map[track_identifier]
                album = library_track.get('Album', '')
                genre = library_track.get('Genre', '')
                if not artist:
                    artist = library_track.get('Artist', '')
                if not title:
                    title = library_track.get('Title', '')

            parsed_tracks.append({
                'source_id': source_id,
                'track_identifier': track_identifier,
                'days_date': days_date,
                'hours': hours,
                'track_description': track_description,
                'artist': artist,
                'title': title,
                'album': album,
                'genre': genre,
                'play_duration_ms': row.get('Play Duration Milliseconds', '0'),
                'media_duration_ms': row.get('Media Duration In Milliseconds', '0'),
                'end_reason': row.get('End Reason Type', ''),
                'source_type': row.get('Source Type', 'UNKNOWN'),
                'play_count': row.get('Play Count', '0'),
                'skip_count': row.get('Skip Count', '0')
            })

        return parsed_tracks

    async def _get_existing_source_ids(self) -> set:
        """Get existing Apple Music source IDs from data_items table"""
        logger.debug(f"[APPLE MUSIC] Querying existing tracks: namespace={self.namespace}")

        existing_items = await self.db_service.async_get_data_items_by_namespace(
            self.namespace,
            limit=100000  # Large limit to get all existing tracks
        )
        existing_ids = {item['source_id'] for item in existing_items}

        logger.debug(f"[APPLE MUSIC] Database returned {len(existing_ids)} existing source IDs")
        return existing_ids

    def _transform_tracks_to_items(self, tracks: List[Dict[str, Any]]) -> List[DataItem]:
        """Transform track dicts to DataItem objects"""
        logger.debug(f"[APPLE MUSIC] Transforming {len(tracks)} tracks to DataItems")

        if not tracks:
            return []

        data_items = []
        for track in tracks:
            try:
                # Build content string
                artist = track.get('artist', 'Unknown Artist')
                title = track.get('title', 'Unknown Track')
                album = track.get('album', '')

                if album:
                    content = f"{artist} - {title} (Album: {album})"
                else:
                    content = f"{artist} - {title}"

                # Parse numeric values
                try:
                    play_duration_ms = int(track.get('play_duration_ms', 0))
                except (ValueError, TypeError):
                    play_duration_ms = 0

                try:
                    media_duration_ms = int(track.get('media_duration_ms', 0))
                except (ValueError, TypeError):
                    media_duration_ms = 0

                try:
                    play_count = int(track.get('play_count', 0))
                except (ValueError, TypeError):
                    play_count = 0

                try:
                    skip_count = int(track.get('skip_count', 0))
                except (ValueError, TypeError):
                    skip_count = 0

                # Create DataItem
                data_item = DataItem(
                    namespace=self.namespace,
                    source_id=track['source_id'],
                    content=content,
                    metadata={
                        'track_identifier': track.get('track_identifier', ''),
                        'track_description': track.get('track_description', ''),
                        'artist': artist,
                        'title': title,
                        'album': album,
                        'genre': track.get('genre', ''),
                        'hours': track.get('hours', ''),
                        'play_duration_ms': play_duration_ms,
                        'media_duration_ms': media_duration_ms,
                        'end_reason': track.get('end_reason', ''),
                        'source_type': track.get('source_type', 'UNKNOWN'),
                        'play_count': play_count,
                        'skip_count': skip_count,
                        'days_date': track.get('days_date', ''),
                        'source_origin': 'apple_music_archive'
                    },
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )

                # Process the item
                processed_item = self.processor.process(data_item)
                data_items.append(processed_item)

            except Exception as e:
                logger.error(f"[APPLE MUSIC] Error creating DataItem for track {track.get('source_id', 'unknown')}: {e}")
                continue

        logger.debug(f"[APPLE MUSIC] Transformation complete: {len(data_items)} DataItems created")
        return data_items

    async def fetch_items(self, since: Optional[datetime] = None, limit: int = 100):
        """
        Fetch Apple Music items from database.
        Apple Music is an on-demand import source, so this fetches existing data.
        """
        logger.debug(f"[APPLE MUSIC] Fetching items: namespace={self.namespace}, limit={limit}")

        items = await self.db_service.async_get_data_items_by_namespace(self.namespace, limit)
        logger.debug(f"[APPLE MUSIC] Retrieved {len(items)} items from database")

        for item in items:
            # Filter by since if provided
            if since and item.get('created_at'):
                item_date = datetime.fromisoformat(item['created_at'])
                if item_date <= since:
                    continue

            # Parse metadata if it's a string
            metadata = item.get('metadata', {})
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    logger.warning(f"[APPLE MUSIC] Failed to parse metadata for item {item['source_id']}")
                    metadata = {}

            yield DataItem(
                namespace=item['namespace'],
                source_id=item['source_id'],
                content=item['content'],
                metadata=metadata,
                created_at=datetime.fromisoformat(item['created_at']) if item.get('created_at') else None,
                updated_at=datetime.fromisoformat(item['updated_at']) if item.get('updated_at') else None
            )

    async def get_item(self, source_id: str) -> Optional[DataItem]:
        """Get specific track play by source ID"""
        logger.debug(f"[APPLE MUSIC] Getting specific item: source_id={source_id}")

        namespaced_id = f"{self.namespace}:{source_id}"
        items = await self.db_service.async_get_data_items_by_ids([namespaced_id])

        if not items:
            logger.debug(f"[APPLE MUSIC] Item not found: {source_id}")
            return None

        item = items[0]

        # Parse metadata if it's a string
        metadata = item.get('metadata', {})
        if isinstance(metadata, str):
            import json
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"[APPLE MUSIC] Failed to parse metadata for item {source_id}")
                metadata = {}

        return DataItem(
            namespace=item['namespace'],
            source_id=item['source_id'],
            content=item['content'],
            metadata=metadata,
            created_at=datetime.fromisoformat(item['created_at']) if item.get('created_at') else None,
            updated_at=datetime.fromisoformat(item['updated_at']) if item.get('updated_at') else None
        )

    def get_source_type(self) -> str:
        """Return the source type identifier"""
        return "apple_music_archive"

    async def test_connection(self) -> bool:
        """Test if Apple Music source is accessible"""
        return self.config.is_configured()
