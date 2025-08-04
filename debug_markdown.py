#!/usr/bin/env python3
"""
Quick script to debug markdown content in the database and test the fixes
"""

import sys
import os
sys.path.insert(0, '.')

from core.database import DatabaseService
import json
import re

def main():
    print("🔍 Debugging Markdown Content in Database")
    print("=" * 50)
    
    db = DatabaseService()
    
    # Get days with limitless data
    days = db.get_days_with_data(namespaces=['limitless'])
    print(f"Found {len(days)} days with limitless data")
    
    if not days:
        print("❌ No days with limitless data found!")
        print("Creating test data...")
        create_test_data(db)
        days = db.get_days_with_data(namespaces=['limitless'])
    
    # Check the most recent day
    date = days[0]
    print(f"\n📅 Checking most recent date: {date}")
    
    # Get raw data items
    items = db.get_data_items_by_date(date, namespaces=['limitless'])
    print(f"Found {len(items)} items for date {date}")
    
    print("\n📋 Item Analysis:")
    print("-" * 30)
    
    for i, item in enumerate(items[:3]):  # Check first 3 items
        print(f"\nItem {i+1}:")
        print(f"  ID: {item.get('id', 'unknown')}")
        print(f"  Namespace: {item.get('namespace')}")
        print(f"  Content length: {len(item.get('content', ''))}")
        
        metadata = item.get('metadata', {})
        if isinstance(metadata, dict):
            print(f"  Has metadata: True")
            print(f"  Metadata keys: {list(metadata.keys())}")
            print(f"  Has title: {'title' in metadata}")
            print(f"  Title: {metadata.get('title', 'None')}")
            print(f"  Has cleaned_markdown: {'cleaned_markdown' in metadata}")
            
            if 'cleaned_markdown' in metadata:
                cleaned_md = metadata['cleaned_markdown']
                print(f"  Cleaned markdown length: {len(cleaned_md)}")
                
                # Check for headers
                has_headers = bool(re.search(r'^#+\s', cleaned_md, re.MULTILINE))
                print(f"  Has headers: {has_headers}")
                
                # Show preview
                preview = cleaned_md[:150] + '...' if len(cleaned_md) > 150 else cleaned_md
                print(f"  Preview: {repr(preview)}")
                
                if has_headers:
                    # Show headers found
                    headers = re.findall(r'^#+\s.+$', cleaned_md, re.MULTILINE)
                    print(f"  Headers found: {headers[:3]}")
        else:
            print(f"  Has metadata: False")
    
    print(f"\n📝 Final Markdown Output:")
    print("-" * 30)
    
    markdown = db.get_markdown_by_date(date, namespaces=['limitless'])
    print(f"Final markdown length: {len(markdown)}")
    
    # Check for headers in final output
    has_final_headers = bool(re.search(r'^#+\s', markdown, re.MULTILINE))
    print(f"Final markdown has headers: {has_final_headers}")
    
    if has_final_headers:
        final_headers = re.findall(r'^#+\s.+$', markdown, re.MULTILINE)
        print(f"Final headers found: {final_headers[:5]}")
    
    print(f"\nFinal markdown preview:")
    preview = markdown[:400] + '...' if len(markdown) > 400 else markdown
    print(repr(preview))
    
    print("\n" + "=" * 50)
    print("✅ Debug analysis complete!")
    
    if has_final_headers:
        print("🎉 SUCCESS: Headers are being generated correctly!")
    else:
        print("⚠️  WARNING: No headers found in final output")
    
    print(f"\n📋 Test the day view at: http://localhost:8000/calendar/day/{date}")
    print(f"📋 Debug API at: http://localhost:8000/calendar/debug/markdown/{date}")

def create_test_data(db):
    """Create some test data with headers for debugging"""
    from datetime import datetime
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Test item with cleaned_markdown
    test_metadata = {
        'title': 'Test Meeting with Headers',
        'start_time': '2024-01-15T10:00:00Z',
        'cleaned_markdown': '# Test Meeting with Headers\n\n*10:00 AM*\n\nThis is a test meeting to verify markdown headers are working correctly.\n\n## Key Discussion Points\n\n- Point 1: Header rendering\n- Point 2: CSS styling\n- Point 3: JavaScript parsing\n\n### Next Steps\n\nEnsure all headers display properly in the day view.'
    }
    
    db.store_data_item(
        id='limitless:test_header_001',
        namespace='limitless',
        source_id='test_header_001',
        content='This is test content with headers',
        metadata=test_metadata,
        days_date=today
    )
    
    print(f"✅ Created test data for {today}")

if __name__ == "__main__":
    main()