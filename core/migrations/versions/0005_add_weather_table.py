MIGRATION_ID = "0005_add_weather_table"
CREATED_AT = "2025-07-28T00:00:00Z"

def up(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS weather (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            days_date TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

def down(connection):
    connection.execute("DROP TABLE IF EXISTS weather")
