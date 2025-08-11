#!/usr/bin/env python3
"""
Check sample conversation data to understand structure
"""
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.database import DatabaseService

def main():
    """Check sample conversation data"""
    database_service = DatabaseService()
    
    with database_service.get_connection() as conn:
        # Get a sample conversation
        cursor = conn.execute("""
            SELECT metadata, content FROM data_items 
            WHERE namespace = 'limitless' 
            AND metadata IS NOT NULL
            LIMIT 3
        """)
        rows = cursor.fetchall()
        
        for i, row in enumerate(rows):
            print(f"\n=== Sample Conversation {i+1} ===")
            
            # Print content summary
            content = row['content'] or ''
            print(f"Content length: {len(content)} characters")
            print(f"Content preview: {content[:200]}...")
            
            # Parse and examine metadata
            metadata = json.loads(row['metadata'])
            
            if 'original_response' in metadata:
                original = metadata['original_response']
                print(f"\nOriginal response keys: {list(original.keys())}")
                
                # Check contents
                contents = original.get('contents', [])
                print(f"Number of content nodes: {len(contents)}")
                
                if contents:
                    print("\nFirst few content nodes:")
                    for j, node in enumerate(contents[:3]):
                        print(f"  Node {j}: type={node.get('type')}, speaker={node.get('speakerName')}")
                        content_text = node.get('content', '')
                        print(f"    Content: {content_text[:100]}...")
                
                # Check for conversations with actual speakers
                speakers = set()
                spoken_lines = []
                for node in contents:
                    speaker = node.get('speakerName')
                    if speaker and node.get('content'):
                        speakers.add(speaker)
                        spoken_lines.append(node.get('content'))
                
                print(f"Unique speakers: {list(speakers)}")
                print(f"Spoken lines count: {len(spoken_lines)}")
                
                if spoken_lines:
                    print("Sample spoken lines:")
                    for line in spoken_lines[:3]:
                        print(f"  - {line[:80]}...")

if __name__ == "__main__":
    main()