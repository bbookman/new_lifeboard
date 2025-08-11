import sqlite3
import json

DB_PATH = "lifeboard.db"
OUTPUT_FILE = "metadata_contents.md"
TRUNCATE_LENGTH = 300

def get_limitless_metadata_sample():
    """
    Connects to the database, retrieves one metadata entry from the data_items
    table where the namespace is 'limitless', truncates markdown fields,
    and writes the result to a file.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT metadata FROM data_items WHERE namespace = 'limitless' LIMIT 1")
        row = cursor.fetchone()

        if row:
            metadata_json = row[0]
            try:
                metadata = json.loads(metadata_json)

                if 'original_lifelog' in metadata and 'markdown' in metadata['original_lifelog']:
                    metadata['original_lifelog']['markdown'] = metadata['original_lifelog']['markdown'][:TRUNCATE_LENGTH]

                if 'cleaned_markdown' in metadata:
                    metadata['cleaned_markdown'] = metadata['cleaned_markdown'][:TRUNCATE_LENGTH]

                with open(OUTPUT_FILE, 'w') as f:
                    f.write(json.dumps(metadata, indent=4))
                print(f"Successfully wrote truncated metadata to {OUTPUT_FILE}")

            except json.JSONDecodeError:
                print("Error: Could not decode JSON from metadata column.")
                with open(OUTPUT_FILE, 'w') as f:
                    f.write("Error: Could not decode JSON from metadata column.\n")
                    f.write("Raw metadata: " + metadata_json)

        else:
            print("No data found for namespace 'limitless'.")
            with open(OUTPUT_FILE, 'w') as f:
                f.write("No data found for namespace 'limitless'.")

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        with open(OUTPUT_FILE, 'w') as f:
            f.write(f"Database error: {e}")

    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    get_limitless_metadata_sample()