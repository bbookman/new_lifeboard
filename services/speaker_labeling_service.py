"""
Speaker Labeling Service

Automatically processes Limitless transcripts through speaker identification LLM prompt
to improve speaker labels and attribution.
"""

import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timezone

from core.base_service import BaseService
from core.database import DatabaseService
from config.models import AppConfig

logger = logging.getLogger(__name__)


class SpeakerLabelingService(BaseService):
    """Service for automatic speaker labeling processing"""

    def __init__(self, database: DatabaseService, config: AppConfig):
        super().__init__(service_name="SpeakerLabelingService", config=config)
        self.database = database
        self.config = config

        # Dependencies
        self.add_dependency("DatabaseService")
        self.add_capability("speaker_labeling")
        self.add_capability("transcript_processing")

        logger.info("SpeakerLabelingService initialized")

    async def process_pending_speaker_labeling(
        self,
        batch_size: int = 10,
        force_reprocess: bool = False
    ) -> Dict[str, Any]:
        """
        Automatically process pending speaker labeling items

        Args:
            batch_size: Number of items to process in this run
            force_reprocess: Reprocess even if already completed

        Returns:
            Dictionary with processing statistics and results
        """
        logger.info(f"Starting speaker labeling batch processing (batch_size={batch_size}, force={force_reprocess})")

        result = {
            "items_processed": 0,
            "items_completed": 0,
            "items_skipped": 0,
            "items_failed": 0,
            "errors": []
        }

        try:
            # Get pending items
            items = await self.get_pending_items(limit=batch_size, force_reprocess=force_reprocess)
            logger.info(f"Found {len(items)} items to process")

            if not items:
                logger.info("No pending items to process")
                return result

            # Process each item
            for item in items:
                try:
                    item_result = await self.process_single_item(item['id'])
                    result["items_processed"] += 1

                    if item_result["status"] == "completed":
                        result["items_completed"] += 1
                    elif item_result["status"] == "skipped":
                        result["items_skipped"] += 1
                    elif item_result["status"] == "failed":
                        result["items_failed"] += 1
                        result["errors"].append(item_result.get("error", "Unknown error"))

                except Exception as e:
                    error_msg = f"Error processing item {item['id']}: {str(e)}"
                    logger.error(error_msg)
                    result["items_failed"] += 1
                    result["errors"].append(error_msg)

            logger.info(f"Batch processing complete: {result['items_completed']} completed, "
                       f"{result['items_skipped']} skipped, {result['items_failed']} failed")

        except Exception as e:
            error_msg = f"Error in batch processing: {str(e)}"
            logger.error(error_msg)
            result["errors"].append(error_msg)

        return result

    async def regenerate_speaker_labeling_for_date(
        self,
        days_date: str
    ) -> Dict[str, Any]:
        """
        Manually regenerate speaker labeling for a specific date

        Args:
            days_date: Date to regenerate (YYYY-MM-DD format)

        Returns:
            Dictionary with regeneration results
        """
        logger.info("=" * 80)
        logger.info("[SERVICE] ===== REGENERATE FOR DATE =====")
        logger.info(f"[SERVICE] Date: {days_date}")
        logger.info(f"[SERVICE] Timestamp: {datetime.now(timezone.utc).isoformat()}")

        result = {
            "success": False,
            "days_date": days_date,
            "items_reprocessed": 0,
            "items_improved": 0,
            "items_skipped": 0,
            "errors": []
        }

        try:
            # Get all limitless data_items for this date
            logger.info(f"[SERVICE] Calling _get_items_for_date('{days_date}')...")
            items = await self._get_items_for_date(days_date)
            logger.info(f"[SERVICE] Found {len(items)} items for date {days_date}")

            if not items:
                logger.info("[SERVICE] No items found, returning success with 0 items")
                result["success"] = True
                logger.info("=" * 80)
                return result

            # Log each item's current status
            for i, item in enumerate(items, 1):
                logger.info(f"[SERVICE] Item {i}/{len(items)}: id={item['id']}")

            # Reset their status to pending
            logger.info(f"[SERVICE] Resetting all {len(items)} items to 'pending' status...")
            for item in items:
                logger.debug(f"[SERVICE] Resetting {item['id']} to pending")
                self.update_speaker_label_status(item['id'], 'pending')
            logger.info(f"[SERVICE] All items reset to pending")

            # Process them
            logger.info(f"[SERVICE] Starting processing of {len(items)} items...")
            for i, item in enumerate(items, 1):
                try:
                    logger.info(f"[SERVICE] Processing item {i}/{len(items)}: {item['id']}")
                    item_result = await self.process_single_item(item['id'])
                    logger.info(f"[SERVICE] Item {i} result: {item_result}")

                    result["items_reprocessed"] += 1

                    if item_result["status"] == "completed":
                        result["items_improved"] += 1
                        logger.info(f"[SERVICE] Item {i} IMPROVED")
                    elif item_result["status"] == "skipped":
                        result["items_skipped"] += 1
                        logger.info(f"[SERVICE] Item {i} SKIPPED")
                    else:
                        logger.warning(f"[SERVICE] Item {i} status: {item_result['status']}")

                except Exception as e:
                    error_msg = f"Error processing item {item['id']}: {str(e)}"
                    logger.error(f"[SERVICE] {error_msg}")
                    logger.error(f"[SERVICE] Exception type: {type(e).__name__}")
                    logger.error(f"[SERVICE] Exception stack:", exc_info=True)
                    result["errors"].append(error_msg)

            result["success"] = True
            logger.info("[SERVICE] ===== REGENERATION COMPLETE =====")
            logger.info(f"[SERVICE] Total items reprocessed: {result['items_reprocessed']}")
            logger.info(f"[SERVICE] Items improved: {result['items_improved']}")
            logger.info(f"[SERVICE] Items skipped: {result['items_skipped']}")
            logger.info(f"[SERVICE] Errors: {len(result['errors'])}")
            logger.info("=" * 80)

        except Exception as e:
            error_msg = f"Error regenerating for date {days_date}: {str(e)}"
            logger.error("=" * 80)
            logger.error("[SERVICE] ===== ERROR IN REGENERATION =====")
            logger.error(f"[SERVICE] {error_msg}")
            logger.error(f"[SERVICE] Exception type: {type(e).__name__}")
            logger.error("[SERVICE] Stack trace:", exc_info=True)
            logger.error("=" * 80)
            result["errors"].append(error_msg)
            result["success"] = False

        return result

    async def get_pending_items(
        self,
        limit: int = 100,
        force_reprocess: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get data items that need speaker labeling

        Args:
            limit: Maximum number of items to return
            force_reprocess: Include already completed items

        Returns:
            List of data items needing processing
        """
        try:
            logger.debug(f"Getting pending items: limit={limit}, force_reprocess={force_reprocess}")

            with self.database.get_connection() as conn:
                if force_reprocess:
                    query = """
                        SELECT id, namespace, source_id, days_date, created_at
                        FROM data_items
                        WHERE namespace = 'limitless'
                        ORDER BY days_date DESC, created_at ASC
                        LIMIT ?
                    """
                else:
                    query = """
                        SELECT id, namespace, source_id, days_date, created_at
                        FROM data_items
                        WHERE namespace = 'limitless'
                        AND speaker_label_status = 'pending'
                        ORDER BY days_date DESC, created_at ASC
                        LIMIT ?
                    """

                logger.debug(f"Executing query: {query.strip()}")
                cursor = conn.execute(query, (limit,))
                results = [dict(row) for row in cursor.fetchall()]
                logger.debug(f"Query returned {len(results)} results")

                return results

        except Exception as e:
            logger.error(f"Error getting pending items: {e}", exc_info=True)
            return []

    async def process_single_item(
        self,
        data_item_id: str
    ) -> Dict[str, Any]:
        """
        Process a single data item through speaker labeling

        Steps:
        1. Get data_item from data_items table
        2. Get corresponding limitless record via source_id
        3. Extract speaker lines from limitless.processed_content
        4. If no speakers, mark as 'skipped' and return
        5. Apply LLM prompt to speaker lines
        6. Reconstruct markdown with improved labels
        7. Store in limitless.speaker_labeled_content
        8. Update data_items.speaker_label_status = 'completed'

        Args:
            data_item_id: ID of data item to process

        Returns:
            Dictionary with processing result
        """
        logger.info(f"Processing item: {data_item_id}")

        result = {
            "success": False,
            "data_item_id": data_item_id,
            "status": "failed",
            "error": None
        }

        try:
            # Mark as processing
            self.update_speaker_label_status(data_item_id, 'processing')

            # Get data_item with metadata
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, namespace, source_id, days_date, metadata
                    FROM data_items
                    WHERE id = ?
                """, (data_item_id,))
                data_item = cursor.fetchone()

                if not data_item:
                    raise ValueError(f"Data item not found: {data_item_id}")

                data_item = dict(data_item)

            # Extract processed markdown from metadata (unified architecture)
            import json
            metadata = json.loads(data_item['metadata']) if data_item.get('metadata') else {}

            # Get cleaned markdown from top-level metadata (Limitless processor stores it here)
            processed_content = metadata.get('cleaned_markdown')

            if not processed_content:
                logger.info(f"No cleaned_markdown in metadata for {data_item_id}, marking as skipped")
                self.update_speaker_label_status(data_item_id, 'skipped')
                result["status"] = "skipped"
                result["success"] = True
                return result

            # Extract speaker lines
            speaker_lines, line_mapping = await self._extract_speaker_lines(processed_content)

            if not speaker_lines:
                logger.info(f"No speaker lines found for {data_item_id}, marking as skipped")
                self.update_speaker_label_status(data_item_id, 'skipped')
                result["status"] = "skipped"
                result["success"] = True
                return result

            logger.info(f"Found {len(speaker_lines)} speaker lines to process")

            # Apply speaker prompt (LLM processing)
            improved_lines = await self._apply_speaker_prompt(speaker_lines)

            # Reconstruct markdown with improved labels
            improved_content = await self._reconstruct_markdown(
                processed_content,
                improved_lines,
                line_mapping
            )

            # Store improved content in metadata at top level (unified architecture)
            metadata['speaker_labeled_content'] = improved_content
            updated_metadata = json.dumps(metadata)

            with self.database.get_connection() as conn:
                conn.execute("""
                    UPDATE data_items
                    SET metadata = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (updated_metadata, data_item_id))
                conn.commit()

            # Update status to completed
            self.update_speaker_label_status(data_item_id, 'completed')

            result["status"] = "completed"
            result["success"] = True
            logger.info(f"Successfully processed item {data_item_id}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Failed to process item {data_item_id}: {error_msg}")
            result["error"] = error_msg
            result["status"] = "failed"

            # Mark as failed in database
            try:
                self.update_speaker_label_status(data_item_id, 'failed')
            except Exception as update_error:
                logger.error(f"Failed to update status to failed: {update_error}")

        return result

    async def _extract_speaker_lines(
        self,
        processed_content: str
    ) -> Tuple[List[str], Dict[int, Dict[str, Any]]]:
        """
        Extract speaker lines from processed_content

        Returns:
            - List of speaker lines (format: "Speaker (date time): text")
            - Mapping dict for reconstruction {line_num: {original, start_pos, end_pos}}
        """
        speaker_lines = []
        line_mapping = {}

        # Pattern to match bullet point lines with speaker format
        # Example: "- You (10/15/25 2:32 PM): Echo, make an announcement."
        # Example: "- Unknown (10/15/25 2:32 PM): Ruffle."
        speaker_pattern = re.compile(r'^-\s+(.+\([0-9/]+\s+[0-9:]+\s+[AP]M\):\s+.+)$')

        lines = processed_content.split('\n')
        for idx, line in enumerate(lines):
            # Check if line starts with '- ' and contains speaker format
            match = speaker_pattern.match(line)
            if match:
                speaker_content = match.group(1)
                speaker_lines.append(speaker_content)
                line_mapping[len(speaker_lines) - 1] = {
                    'original': line,
                    'line_num': idx,
                    'speaker_content': speaker_content
                }

        return speaker_lines, line_mapping

    async def _apply_speaker_prompt(
        self,
        speaker_lines: List[str]
    ) -> str:
        """
        Send speaker lines to LLM with SPEAKER LABELING prompt

        Args:
            speaker_lines: List of speaker lines to process

        Returns:
            Labeled transcript as plain text
        """
        logger.info(f"Applying speaker prompt to {len(speaker_lines)} lines")

        try:
            # Get the speaker labeling prompt
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT d.content_md
                    FROM prompt_settings ps
                    JOIN user_documents d ON d.id = ps.prompt_document_id
                    WHERE ps.setting_key = 'speaker_labeling_prompt_default'
                    AND ps.is_active = TRUE
                """)
                prompt_row = cursor.fetchone()

                if not prompt_row:
                    raise ValueError("Speaker labeling prompt not found")

                prompt_content = prompt_row['content_md']

            # Prepare the speaker lines as input
            transcript_input = "\n".join(speaker_lines)

            # Get LLM provider
            from llm.factory import LLMProviderFactory
            llm_factory = LLMProviderFactory(self.config.llm_provider)
            llm_provider = await llm_factory.get_active_provider()

            if not llm_provider:
                raise ValueError("LLM provider not available")

            # Generate improved speaker labels
            logger.info("Sending transcript to LLM for speaker labeling")
            response = await llm_provider.generate_response(
                prompt=prompt_content,
                context=transcript_input,
                max_tokens=2000,
                temperature=0.3  # Lower temperature for more consistent labeling
            )

            logger.info(f"Received improved speaker labels ({len(response.content)} chars)")
            return response.content

        except Exception as e:
            logger.error(f"Error applying speaker prompt: {e}")
            # Return original lines if LLM fails
            return "\n".join(speaker_lines)

    async def _reconstruct_markdown(
        self,
        original_markdown: str,
        improved_lines: str,
        line_mapping: Dict[int, Dict[str, Any]]
    ) -> str:
        """
        Replace speaker lines in original markdown with improved versions

        Args:
            original_markdown: Original markdown content
            improved_lines: Improved speaker lines from LLM (plain text)
            line_mapping: Mapping of line indices to original positions

        Returns:
            Markdown with improved speaker labels
        """
        logger.info("Reconstructing markdown with improved speaker labels")

        try:
            # Split improved lines
            improved_list = [line.strip() for line in improved_lines.split('\n') if line.strip()]

            # Split original markdown into lines
            original_lines = original_markdown.split('\n')

            # Replace speaker lines
            for idx, improved_line in enumerate(improved_list):
                if idx in line_mapping:
                    mapping = line_mapping[idx]
                    line_num = mapping['line_num']

                    # Reconstruct as bullet point (preserving original format)
                    original_lines[line_num] = f"- {improved_line}"

            # Join back together
            reconstructed = '\n'.join(original_lines)

            logger.info("Markdown reconstruction complete")
            return reconstructed

        except Exception as e:
            logger.error(f"Error reconstructing markdown: {e}")
            # Return original if reconstruction fails
            return original_markdown

    def update_speaker_label_status(
        self,
        data_item_id: str,
        status: str
    ):
        """
        Update speaker_label_status for a data item

        Args:
            data_item_id: ID of data item
            status: New status ('pending', 'processing', 'completed', 'skipped', 'failed')
        """
        try:
            with self.database.get_connection() as conn:
                conn.execute("""
                    UPDATE data_items
                    SET speaker_label_status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, data_item_id))
                conn.commit()

            logger.debug(f"Updated speaker_label_status to '{status}' for {data_item_id}")

        except Exception as e:
            logger.error(f"Error updating speaker label status: {e}")
            raise

    async def _get_items_for_date(
        self,
        days_date: str
    ) -> List[Dict[str, Any]]:
        """
        Get all limitless data_items for a specific date

        Args:
            days_date: Date to query (YYYY-MM-DD format)

        Returns:
            List of data items for the date
        """
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, namespace, source_id, days_date
                    FROM data_items
                    WHERE namespace = 'limitless'
                    AND days_date = ?
                    ORDER BY created_at ASC
                """, (days_date,))
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting items for date {days_date}: {e}")
            return []

    async def get_speaker_labeling_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about speaker labeling processing

        Returns:
            Dictionary with processing statistics
        """
        try:
            with self.database.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT
                        speaker_label_status,
                        COUNT(*) as count
                    FROM data_items
                    WHERE namespace = 'limitless'
                    GROUP BY speaker_label_status
                """)

                stats = {row['speaker_label_status']: row['count'] for row in cursor.fetchall()}

                return {
                    "total": sum(stats.values()),
                    "by_status": stats,
                    "pending_count": stats.get('pending', 0),
                    "completed_count": stats.get('completed', 0),
                    "skipped_count": stats.get('skipped', 0),
                    "failed_count": stats.get('failed', 0)
                }

        except Exception as e:
            logger.error(f"Error getting speaker labeling statistics: {e}")
            return {
                "total": 0,
                "by_status": {},
                "pending_count": 0,
                "completed_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "error": str(e)
            }

    async def _initialize_service(self) -> bool:
        """Initialize the speaker labeling service"""
        logger.info("Initializing SpeakerLabelingService")
        return True

    async def _shutdown_service(self) -> bool:
        """Shutdown the speaker labeling service"""
        logger.info("Shutting down SpeakerLabelingService")
        return True

    async def _check_service_health(self) -> Dict[str, Any]:
        """Check service health"""
        try:
            stats = await self.get_speaker_labeling_statistics()
            return {
                "healthy": True,
                "statistics": stats
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e)
            }
