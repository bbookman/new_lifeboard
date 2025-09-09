"""
Test for Spotify tokens database migration (0015)

Following TDD approach - these tests should fail initially (RED phase)
until the migration is implemented.
"""

import pytest
import sqlite3
from unittest.mock import Mock
import tempfile
import os

# Mock migration import - will fail until migration is created
try:
    from core.migrations.versions.migration_0015_add_spotify_tokens_table import (
        upgrade, downgrade, get_migration_info
    )
except ImportError:
    upgrade = None
    downgrade = None
    get_migration_info = None


class TestSpotifyTokensMigration:
    """Test suite for Spotify tokens database migration"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp()
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        yield conn
        conn.close()
        os.close(fd)
        os.unlink(path)
    
    @pytest.fixture
    def db_cursor(self, temp_db):
        """Get cursor for test database"""
        return temp_db.cursor()
    
    def test_migration_info_exists(self):
        """Test that migration info is properly defined"""
        # RED: This will fail until migration file is created
        assert get_migration_info is not None, "Migration file not found"
        
        info = get_migration_info()
        assert info["id"] == "0015"
        assert info["name"] == "add_spotify_tokens"
        assert "0014" in info["dependencies"]
    
    def test_migration_creates_table_with_constraints(self, db_cursor):
        """Test table creation with proper constraints"""
        # RED: This will fail - table doesn't exist yet
        if upgrade is None:
            pytest.skip("Migration not implemented yet")
        
        # Run the upgrade migration
        upgrade(db_cursor)
        
        # Check if table exists
        cursor = db_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='spotify_tokens'
        """)
        assert cursor.fetchone() is not None, "spotify_tokens table not created"
        
        # Check table schema
        cursor = db_cursor.execute("PRAGMA table_info(spotify_tokens)")
        columns = {row[1]: row for row in cursor.fetchall()}
        
        # Verify required columns exist
        expected_columns = [
            'id', 'access_token', 'refresh_token', 'expires_at',
            'scope', 'created_at', 'updated_at'
        ]
        
        for col in expected_columns:
            assert col in columns, f"Column {col} missing from spotify_tokens table"
        
        # Verify primary key
        assert columns['id'][5] == 1, "id column should be primary key"
        
        # Verify NOT NULL constraints
        assert columns['access_token'][3] == 1, "access_token should be NOT NULL"
        assert columns['expires_at'][3] == 1, "expires_at should be NOT NULL"
    
    def test_migration_creates_indexes(self, db_cursor):
        """Test index creation for performance"""
        # RED: This will fail - indexes don't exist yet
        if upgrade is None:
            pytest.skip("Migration not implemented yet")
        
        upgrade(db_cursor)
        
        # Check for expires_at index
        cursor = db_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_spotify_tokens_expires_at'
        """)
        assert cursor.fetchone() is not None, "expires_at index not found"
        
        # Check for updated_at index
        cursor = db_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_spotify_tokens_updated_at'
        """)
        assert cursor.fetchone() is not None, "updated_at index not found"
    
    def test_migration_rollback_removes_table(self, db_cursor):
        """Test rollback functionality"""
        # RED: This will fail - rollback not implemented
        if upgrade is None or downgrade is None:
            pytest.skip("Migration not implemented yet")
        
        # First create the table
        upgrade(db_cursor)
        
        # Verify table exists
        cursor = db_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='spotify_tokens'
        """)
        assert cursor.fetchone() is not None, "Table should exist after upgrade"
        
        # Run downgrade
        downgrade(db_cursor)
        
        # Verify table is removed
        cursor = db_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='spotify_tokens'
        """)
        assert cursor.fetchone() is None, "Table should be removed after downgrade"
        
        # Verify indexes are also removed
        cursor = db_cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name LIKE 'idx_spotify_tokens_%'
        """)
        assert cursor.fetchall() == [], "Indexes should be removed after downgrade"
    
    def test_constraint_validation(self, db_cursor):
        """Test database constraints work correctly"""
        # RED: This will fail - constraints not enforced yet
        if upgrade is None:
            pytest.skip("Migration not implemented yet")
        
        upgrade(db_cursor)
        
        # Test NOT NULL constraint on access_token
        with pytest.raises(sqlite3.IntegrityError):
            db_cursor.execute("""
                INSERT INTO spotify_tokens (refresh_token, expires_at, scope)
                VALUES ('refresh_token', '2024-12-31 23:59:59', 'user-read-recently-played')
            """)
        
        # Test NOT NULL constraint on expires_at
        with pytest.raises(sqlite3.IntegrityError):
            db_cursor.execute("""
                INSERT INTO spotify_tokens (access_token, refresh_token, scope)
                VALUES ('access_token', 'refresh_token', 'user-read-recently-played')
            """)
        
        # Note: valid_expiry constraint removed from migration for SQLite compatibility
        # Application-level validation will handle this constraint instead
        pass
    
    def test_successful_token_insertion(self, db_cursor):
        """Test that valid tokens can be inserted successfully"""
        # RED: This will fail until migration is implemented
        if upgrade is None:
            pytest.skip("Migration not implemented yet")
        
        upgrade(db_cursor)
        
        # Insert valid token data (use future date to satisfy constraint)
        from datetime import datetime, timedelta
        future_expiry = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        
        db_cursor.execute("""
            INSERT INTO spotify_tokens (access_token, refresh_token, expires_at, scope)
            VALUES (?, ?, ?, ?)
        """, (
            'test_access_token',
            'test_refresh_token', 
            future_expiry,
            'user-read-recently-played'
        ))
        
        # Verify insertion
        cursor = db_cursor.execute("SELECT * FROM spotify_tokens WHERE id = 1")
        row = cursor.fetchone()
        
        assert row is not None, "Token should be inserted successfully"
        assert row[1] == 'test_access_token', "Access token should match"
        assert row[2] == 'test_refresh_token', "Refresh token should match"
        assert row[4] == 'user-read-recently-played', "Scope should match"
    
    def test_multiple_tokens_handling(self, db_cursor):
        """Test behavior with multiple token entries"""
        # RED: This will fail until migration is implemented
        if upgrade is None:
            pytest.skip("Migration not implemented yet")
        
        upgrade(db_cursor)
        
        # Use future dates to satisfy constraint
        from datetime import datetime, timedelta
        future_expiry1 = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
        future_expiry2 = (datetime.now() + timedelta(hours=2)).strftime('%Y-%m-%d %H:%M:%S')
        
        # Insert first token
        db_cursor.execute("""
            INSERT INTO spotify_tokens (access_token, refresh_token, expires_at, scope)
            VALUES ('token1', 'refresh1', ?, 'scope1')
        """, (future_expiry1,))
        
        # Insert second token (simulating token refresh/update)
        db_cursor.execute("""
            INSERT INTO spotify_tokens (access_token, refresh_token, expires_at, scope)
            VALUES ('token2', 'refresh2', ?, 'scope2')
        """, (future_expiry2,))
        
        # Verify both tokens exist
        cursor = db_cursor.execute("SELECT COUNT(*) FROM spotify_tokens")
        count = cursor.fetchone()[0]
        assert count == 2, "Both tokens should be stored"
        
        # Verify we can query by different criteria (token2 has later expiry)
        cursor = db_cursor.execute("""
            SELECT access_token FROM spotify_tokens 
            WHERE expires_at = ?
        """, (future_expiry2,))
        result = cursor.fetchone()
        assert result[0] == 'token2', "Should find token2 by expiry date"


if __name__ == "__main__":
    # Run tests to verify they fail (RED phase)
    pytest.main([__file__, "-v"])