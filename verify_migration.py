#!/usr/bin/env python3
"""
Verify database migration results
"""
import sys
import os
import json
import sqlite3

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """Verify migration results"""
    # Connect to database
    conn = sqlite3.connect("lifeboard.db")
    conn.row_factory = sqlite3.Row
    
    try:
        # Check new columns exist
        cursor = conn.execute("PRAGMA table_info(data_items)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print("Checking new columns exist:")
        required_columns = ['semantic_status', 'semantic_processed_at', 'processing_priority']
        for col in required_columns:
            if col in columns:
                print(f"✅ Column '{col}' exists")
            else:
                print(f"❌ Column '{col}' missing")
        
        # Check data migration
        print("\nChecking data migration:")
        cursor = conn.execute("""
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN semantic_status = 'pending' THEN 1 ELSE 0 END) as pending_count
            FROM data_items WHERE namespace = 'limitless'
        """)
        row = cursor.fetchone()
        print(f"Total limitless records: {row['total']}")
        print(f"Pending semantic processing: {row['pending_count']}")
        
        # Check metadata structure
        print("\nChecking metadata structure:")
        cursor = conn.execute("""
            SELECT metadata FROM data_items 
            WHERE namespace = 'limitless' AND metadata IS NOT NULL 
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if row:
            metadata = json.loads(row['metadata'])
            
            if 'original_response' in metadata and 'processed_response' in metadata:
                print("✅ Two-key metadata structure confirmed")
                print(f"✅ Original response keys: {list(metadata['original_response'].keys())[:5]}...")
                print(f"✅ Processed response keys: {list(metadata['processed_response'].keys())}")
                
                # Check semantic metadata structure
                processed = metadata['processed_response']
                if 'semantic_metadata' in processed and 'processed' in processed['semantic_metadata']:
                    print(f"✅ Semantic metadata: processed={processed['semantic_metadata']['processed']}")
                if 'display_conversation' in processed:
                    print(f"✅ Display conversation placeholder: {len(processed['display_conversation'])} items")
                if 'semantic_clusters' in processed:
                    print(f"✅ Semantic clusters placeholder: {len(processed['semantic_clusters'])} items")
            else:
                print("❌ Two-key metadata structure not found")
                print(f"Available keys: {list(metadata.keys())}")
        else:
            print("❌ No limitless records found")
        
        print("\nMigration verification completed!")
        
    except Exception as e:
        print(f"Error during verification: {e}")
        return 1
    finally:
        conn.close()
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)