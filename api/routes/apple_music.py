"""
Apple Music API routes for retrieving Apple Music listening history.
"""
import logging
import json
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from core.dependencies import get_startup_service_dependency
from services.startup import StartupService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/apple-music", tags=["apple-music"])


class AppleMusicPlay(BaseModel):
    """Apple Music play record model."""
    artist: str
    album: str
    song: str
    play_count: int


@router.get("/{days_date}", response_model=List[AppleMusicPlay])
async def get_apple_music_plays(
    days_date: str = Path(..., description="Date in YYYY-MM-DD format"),
    startup_service: StartupService = Depends(get_startup_service_dependency)
):
    """
    Get Apple Music plays for a specific date, aggregated and sorted by play count.

    Returns a list of play records sorted by play_count descending (most plays first).
    """
    try:
        logger.info(f"Getting Apple Music plays for date: {days_date}")

        # Validate date format
        if not _validate_date_format(days_date):
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

        # Query data_items for Apple Music data
        query = """
            SELECT id, namespace, source_id, content, metadata, days_date
            FROM data_items
            WHERE namespace = ? AND days_date = ?
        """
        params = ["apple_music", days_date]

        with startup_service.database.get_connection() as conn:
            cursor = conn.execute(query, params)

            # Aggregate plays by (artist, album, song)
            plays_dict: Dict[tuple, int] = {}

            for row in cursor.fetchall():
                # Parse metadata
                metadata = {}
                if row["metadata"]:
                    try:
                        metadata = json.loads(row["metadata"]) if isinstance(row["metadata"], str) else row["metadata"]
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Failed to parse metadata for item {row['id']}")
                        continue

                # Extract fields
                artist = metadata.get("artist", "Unknown Artist")
                album = metadata.get("album", "Unknown Album")
                song = metadata.get("title", "Unknown Song")
                play_count = metadata.get("play_count", 1)

                # Aggregate by (artist, album, song)
                key = (artist, album, song)
                if key in plays_dict:
                    plays_dict[key] += play_count
                else:
                    plays_dict[key] = play_count

            # Convert to list of AppleMusicPlay objects
            plays = [
                AppleMusicPlay(
                    artist=artist,
                    album=album,
                    song=song,
                    play_count=count
                )
                for (artist, album, song), count in plays_dict.items()
            ]

            # Sort by play_count descending (most plays first)
            plays.sort(key=lambda x: x.play_count, reverse=True)

        logger.info(f"Retrieved {len(plays)} aggregated Apple Music plays for {days_date}")
        return plays

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching Apple Music plays: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _validate_date_format(date_str: str) -> bool:
    """Validate date string format (YYYY-MM-DD)."""
    from datetime import datetime
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False
