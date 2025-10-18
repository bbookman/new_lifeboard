#!/usr/bin/env python3
"""
Diagnostic script to check speaker labeling status for a specific date

Usage:
    python3 scripts/check_speaker_status.py [date]

    If no date provided, uses 2025-10-16 as default
"""

import sqlite3
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DB_PATH = project_root / "lifeboard.db"


def check_speaker_status(date: str):
    """Check speaker labeling status for a specific date"""
    print("=" * 80)
    print(f"SPEAKER LABELING STATUS CHECK - {date}")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Database: {DB_PATH}")
    print("=" * 80)
    print()

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get all limitless items for the date
    cursor.execute("""
        SELECT id, source_id, speaker_label_status,
               LENGTH(content) as content_length,
               LENGTH(metadata) as metadata_length,
               created_at, updated_at
        FROM data_items
        WHERE namespace = 'limitless' AND days_date = ?
        ORDER BY created_at
    """, (date,))

    items = cursor.fetchall()
    print(f"Found {len(items)} limitless items for {date}:\n")

    if not items:
        print("  (No items found)")
        conn.close()
        print("=" * 80)
        return

    for i, item in enumerate(items, 1):
        print(f"Item {i}:")
        print(f"  ID: {item['id']}")
        print(f"  Source ID: {item['source_id']}")
        print(f"  Status: {item['speaker_label_status']}")
        print(f"  Content: {item['content_length']} bytes")
        print(f"  Metadata: {item['metadata_length']} bytes")
        print(f"  Created: {item['created_at']}")
        print(f"  Updated: {item['updated_at']}")
        print()

    # Status summary
    print("\nStatus Summary:")
    print("-" * 40)
    cursor.execute("""
        SELECT speaker_label_status, COUNT(*) as count
        FROM data_items
        WHERE namespace = 'limitless' AND days_date = ?
        GROUP BY speaker_label_status
        ORDER BY speaker_label_status
    """, (date,))

    total = 0
    for row in cursor.fetchall():
        status = row['speaker_label_status'] or '(null)'
        count = row['count']
        total += count
        print(f"  {status:15s}: {count:3d}")

    print(f"  {'Total':15s}: {total:3d}")
    print()

    # Calculate completion percentage
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN speaker_label_status = 'completed' THEN 1 ELSE 0 END) as completed
        FROM data_items
        WHERE namespace = 'limitless' AND days_date = ?
    """, (date,))

    stats = cursor.fetchone()
    if stats['total'] > 0:
        completion_pct = (stats['completed'] / stats['total']) * 100
        print(f"Completion: {stats['completed']}/{stats['total']} ({completion_pct:.1f}%)")
        print()

        # Show badge status
        all_labeled = stats['completed'] == stats['total']
        print(f"\"Speakers labeled\" badge should appear: {'YES' if all_labeled else 'NO'}")
        if not all_labeled:
            print(f"  (Need {stats['total'] - stats['completed']} more items to complete)")
    print()

    # Check if any items have speaker_labeled_content in metadata
    print("\nMetadata Analysis:")
    print("-" * 40)
    cursor.execute("""
        SELECT id, metadata
        FROM data_items
        WHERE namespace = 'limitless' AND days_date = ?
    """, (date,))

    has_speaker_labeled = 0
    has_cleaned_markdown = 0
    for row in cursor.fetchall():
        try:
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
            if 'speaker_labeled_content' in metadata:
                has_speaker_labeled += 1
            if 'cleaned_markdown' in metadata:
                has_cleaned_markdown += 1
        except json.JSONDecodeError:
            pass

    print(f"Items with 'speaker_labeled_content': {has_speaker_labeled}/{len(items)}")
    print(f"Items with 'cleaned_markdown': {has_cleaned_markdown}/{len(items)}")
    print()

    conn.close()
    print("=" * 80)


if __name__ == "__main__":
    # Get date from command line or use default
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        target_date = "2025-10-16"

    check_speaker_status(target_date)
