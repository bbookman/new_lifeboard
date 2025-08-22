"""Two-key metadata migration

Revision ID: 0007
Revises: 0006
Create Date: 2025-01-11 12:00:00.000000

Migrates existing limitless metadata from mixed structure to clean two-key architecture:
- original_response: Complete unmodified Limitless API response
- processed_response: All processing results including semantic deduplication
"""
import json
from typing import Any, Dict

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    """Migrate to two-key metadata structure and add semantic processing status"""

    # Add new columns for semantic processing status tracking
    op.add_column("data_items", sa.Column("semantic_status", sa.Text(), default="pending"))
    op.add_column("data_items", sa.Column("semantic_processed_at", sa.DateTime()))
    op.add_column("data_items", sa.Column("processing_priority", sa.Integer(), default=1))

    # Create indexes for efficient status queries
    op.create_index("idx_semantic_status_date", "data_items", ["semantic_status", "days_date"])
    op.create_index("idx_processed_at", "data_items", ["semantic_processed_at"])
    op.create_index("idx_semantic_queue", "data_items",
                    ["semantic_status", "processing_priority", "days_date", "created_at"])

    # Get database connection for data migration
    connection = op.get_bind()

    # Migrate existing metadata structure
    print("Starting metadata migration to two-key structure...")

    # Get all limitless records that need migration
    result = connection.execute(
        "SELECT id, metadata FROM data_items WHERE namespace = 'limitless' AND metadata IS NOT NULL",
    )

    migrated_count = 0
    error_count = 0

    for row in result:
        try:
            # Parse existing metadata
            old_metadata = json.loads(row.metadata) if row.metadata else {}

            # Create new two-key structure
            new_metadata = migrate_metadata_to_two_key(old_metadata)

            # Update record with new structure
            connection.execute(
                "UPDATE data_items SET metadata = ?, semantic_status = 'pending', processing_priority = ? WHERE id = ?",
                (json.dumps(new_metadata), determine_priority(old_metadata), row.id),
            )

            migrated_count += 1

            if migrated_count % 100 == 0:
                print(f"Migrated {migrated_count} records...")

        except Exception as e:
            print(f"Error migrating record {row.id}: {e}")
            error_count += 1
            continue

    print(f"Migration completed: {migrated_count} records migrated, {error_count} errors")


def migrate_metadata_to_two_key(old_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert old mixed metadata structure to clean two-key architecture
    
    Args:
        old_metadata: Existing metadata with mixed original/processed data
        
    Returns:
        New metadata with original_response and processed_response keys
    """
    # Extract original Limitless API response
    original_lifelog = old_metadata.get("original_lifelog", {})

    # Create processed response from existing processed fields
    processed_response = {
        # Processing metadata
        "processing_history": old_metadata.get("processing_history", []),
        "semantic_metadata": {"processed": False},  # Will be updated when semantic processing runs

        # Basic extracted fields (from original processors)
        "title": old_metadata.get("title"),
        "start_time": old_metadata.get("start_time"),
        "end_time": old_metadata.get("end_time"),
        "is_starred": old_metadata.get("is_starred", False),
        "updated_at": old_metadata.get("updated_at"),
        "speakers": old_metadata.get("speakers", []),
        "content_types": old_metadata.get("content_types", []),
        "has_markdown": old_metadata.get("has_markdown", False),
        "node_count": old_metadata.get("node_count", 0),

        # Content statistics
        "content_stats": old_metadata.get("content_stats", {}),
        "duration_seconds": old_metadata.get("duration_seconds"),
        "duration_minutes": old_metadata.get("duration_minutes"),
        "conversation_metadata": old_metadata.get("conversation_metadata", {}),

        # Segmentation data
        "segmentation": old_metadata.get("segmentation", {}),

        # Cleaned content (if exists)
        "cleaned_markdown": old_metadata.get("cleaned_markdown"),

        # Semantic deduplication placeholders (will be populated when processing runs)
        "display_conversation": [],
        "semantic_clusters": {},
    }

    # Remove None values from processed_response
    processed_response = {k: v for k, v in processed_response.items() if v is not None}

    # Create new two-key structure
    new_metadata = {
        "original_response": original_lifelog,
        "processed_response": processed_response,
    }

    return new_metadata


def determine_priority(old_metadata: Dict[str, Any]) -> int:
    """
    Determine processing priority based on metadata
    
    Returns:
        3: Urgent (recent conversations)
        2: High (this week)
        1: Normal (older conversations)
    """
    # Try to get start time for priority calculation
    start_time_str = old_metadata.get("start_time")
    if not start_time_str:
        return 1  # Normal priority for conversations without timestamps

    try:
        # Parse start time
        if start_time_str.endswith("Z"):
            start_time_str = start_time_str.replace("Z", "+00:00")

        from datetime import datetime, timedelta, timezone
        start_time = datetime.fromisoformat(start_time_str)
        now = datetime.now(timezone.utc)

        # Calculate age
        age = now - start_time

        if age <= timedelta(days=2):
            return 3  # Urgent: today/yesterday
        if age <= timedelta(days=7):
            return 2  # High: this week
        return 1  # Normal: older

    except Exception:
        return 1  # Default to normal priority if date parsing fails


def downgrade():
    """Revert migration - restore original mixed metadata structure"""

    print("Reverting two-key metadata migration...")

    # Get database connection
    connection = op.get_bind()

    # Get all limitless records with two-key structure
    result = connection.execute(
        "SELECT id, metadata FROM data_items WHERE namespace = 'limitless' AND metadata IS NOT NULL",
    )

    reverted_count = 0

    for row in result:
        try:
            # Parse two-key metadata
            new_metadata = json.loads(row.metadata) if row.metadata else {}

            # Restore original mixed structure
            old_metadata = revert_metadata_to_mixed(new_metadata)

            # Update record
            connection.execute(
                "UPDATE data_items SET metadata = ? WHERE id = ?",
                (json.dumps(old_metadata), row.id),
            )

            reverted_count += 1

        except Exception as e:
            print(f"Error reverting record {row.id}: {e}")
            continue

    print(f"Reverted {reverted_count} records")

    # Drop added columns and indexes
    op.drop_index("idx_semantic_queue")
    op.drop_index("idx_processed_at")
    op.drop_index("idx_semantic_status_date")
    op.drop_column("data_items", "processing_priority")
    op.drop_column("data_items", "semantic_processed_at")
    op.drop_column("data_items", "semantic_status")


def revert_metadata_to_mixed(new_metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Revert two-key structure back to original mixed structure
    
    Args:
        new_metadata: Two-key metadata structure
        
    Returns:
        Original mixed metadata structure
    """
    original_response = new_metadata.get("original_response", {})
    processed_response = new_metadata.get("processed_response", {})

    # Combine into mixed structure (original format)
    old_metadata = {
        "original_lifelog": original_response,
        **processed_response,  # Spread processed fields at top level
    }

    # Remove semantic deduplication fields (they didn't exist in original)
    fields_to_remove = ["display_conversation", "semantic_clusters"]
    for field in fields_to_remove:
        old_metadata.pop(field, None)

    # Clean semantic_metadata if it only contains 'processed: false'
    semantic_metadata = old_metadata.get("semantic_metadata", {})
    if semantic_metadata == {"processed": False}:
        old_metadata.pop("semantic_metadata", None)

    return old_metadata
