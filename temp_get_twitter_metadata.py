import sys
import os
import json

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '')))

from core.database import DatabaseService

db_path = os.getenv("LIFEBOARD_DB_PATH", "lifeboard.db")
db_service = DatabaseService(db_path)

try:
    twitter_items = db_service.get_data_items_by_namespace('twitter', limit=1)

    if twitter_items:
        item = twitter_items[0]
        print(f"Found one Twitter item (ID: {item.get('id')})")
        metadata = item.get('metadata') # metadata is already a dictionary
        if metadata:
            print("\nMetadata Keys and Values:")
            for key, value in metadata.items():
                print(f"  {key}: {value}")
        else:
            print("No metadata found for this Twitter item.")
    else:
        print("No data items found for namespace 'twitter'.")

except Exception as e:
    print(f"An error occurred: {e}")