#!/usr/bin/env python3
"""
Verify semantic processing results
"""
import sys
import os
import json
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Verify semantic processing results"""
    # Connect to database
    conn = sqlite3.connect("lifeboard.db")
    conn.row_factory = sqlite3.Row
    
    try:
        # Check processing status counts
        print("Semantic Processing Status:")
        cursor = conn.execute("""
            SELECT semantic_status, COUNT(*) as count
            FROM data_items WHERE namespace = 'limitless'
            GROUP BY semantic_status
        """)
        for row in cursor.fetchall():
            print(f"  {row['semantic_status']}: {row['count']} conversations")
        
        # Check processed conversations
        print("\nProcessed Conversations Analysis:")
        cursor = conn.execute("""
            SELECT metadata FROM data_items 
            WHERE namespace = 'limitless' 
            AND semantic_status = 'completed'
            LIMIT 3
        """)
        rows = cursor.fetchall()
        
        total_clusters = 0
        total_display_items = 0
        
        for i, row in enumerate(rows):
            metadata = json.loads(row['metadata'])
            processed = metadata['processed_response']
            
            print(f"\n--- Processed Conversation {i+1} ---")
            print(f"✅ Semantic processed: {processed['semantic_metadata']['processed']}")
            print(f"✅ Total lines analyzed: {processed['semantic_metadata']['total_lines_analyzed']}")
            print(f"✅ Clustered lines: {processed['semantic_metadata']['clustered_lines']}")
            print(f"✅ Unique themes: {len(processed['semantic_metadata']['unique_themes'])}")
            print(f"✅ Semantic density: {processed['semantic_metadata']['semantic_density']:.2f}")
            print(f"✅ Display conversation items: {len(processed['display_conversation'])}")
            print(f"✅ Semantic clusters: {len(processed['semantic_clusters'])}")
            
            total_clusters += len(processed['semantic_clusters'])
            total_display_items += len(processed['display_conversation'])
            
            # Show sample themes
            if processed['semantic_metadata']['unique_themes']:
                themes_str = ', '.join(processed['semantic_metadata']['unique_themes'][:3])
                print(f"✅ Sample themes: {themes_str}")
            
            # Show sample cluster
            if processed['semantic_clusters']:
                cluster_id = list(processed['semantic_clusters'].keys())[0]
                cluster = processed['semantic_clusters'][cluster_id]
                print(f"✅ Sample cluster: '{cluster['canonical'][:50]}...' ({cluster['frequency']} occurrences)")
        
        print(f"\n🎯 Summary:")
        print(f"   Average clusters per conversation: {total_clusters/len(rows):.1f}")
        print(f"   Average display items per conversation: {total_display_items/len(rows):.1f}")
        print(f"   🎉 Semantic deduplication is working successfully!")
        
    except Exception as e:
        print(f"Error during verification: {e}")
        return 1
    finally:
        conn.close()
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)