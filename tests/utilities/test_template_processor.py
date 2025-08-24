"""
Tests for Template Processor Service

This test suite covers template variable parsing, resolution, caching, and API integration
for the prompt template system.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock

from services.template_processor import TemplateProcessor, TemplateVariable, ResolvedTemplate
from core.database import DatabaseService
from config.models import AppConfig


class TestTemplateProcessor:
    """Test suite for TemplateProcessor service"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create in-memory database for testing
        self.db_service = DatabaseService(":memory:")
        
        # Create mock config
        self.mock_config = Mock(spec=AppConfig)
        
        # Sample test data
        self.sample_data_items = [
            {
                'id': 'limitless:item1',
                'namespace': 'limitless',
                'source_id': 'item1',
                'content': 'Sample limitless content for today',
                'days_date': '2024-01-15',
                'created_at': '2024-01-15 10:00:00'
            },
            {
                'id': 'twitter:item1',
                'namespace': 'twitter',
                'source_id': 'item1', 
                'content': 'Sample twitter content',
                'days_date': '2024-01-15',
                'created_at': '2024-01-15 11:00:00'
            },
            {
                'id': 'news:item1',
                'namespace': 'news',
                'source_id': 'item1',
                'content': 'Sample news content',
                'days_date': '2024-01-15',
                'created_at': '2024-01-15 12:00:00'
            }
        ]
        
        # Add sample data to database
        for item in self.sample_data_items:
            self.db_service.store_data_item(
                id=item['id'],
                namespace=item['namespace'],
                source_id=item['source_id'],
                content=item['content'],
                days_date=item['days_date']
            )
        
        # Initialize template processor
        self.processor = TemplateProcessor(
            database=self.db_service,
            config=self.mock_config,
            timezone='UTC',
            cache_enabled=False  # Disable cache for most tests
        )
    
    def test_parse_template_variables_valid_patterns(self):
        """Test parsing of valid template variable patterns"""
        content = "Hello {{LIMITLESS_DAY}} and {{TWITTER_WEEK}} and {{NEWS_MONTH}}"
        
        variables = self.processor.parse_template_variables(content)
        
        assert len(variables) == 3
        
        # Check first variable
        assert variables[0].source == 'LIMITLESS'
        assert variables[0].time_range == 'DAY'
        assert variables[0].full_match == '{{LIMITLESS_DAY}}'
        
        # Check second variable
        assert variables[1].source == 'TWITTER'
        assert variables[1].time_range == 'WEEK'
        assert variables[1].full_match == '{{TWITTER_WEEK}}'
        
        # Check third variable
        assert variables[2].source == 'NEWS'
        assert variables[2].time_range == 'MONTH'
        assert variables[2].full_match == '{{NEWS_MONTH}}'
    
    def test_parse_template_variables_invalid_patterns(self):
        """Test parsing ignores invalid template patterns"""
        content = "Hello {{INVALID_SOURCE}} and {{LIMITLESS_INVALID_RANGE}} and {MALFORMED}"
        
        variables = self.processor.parse_template_variables(content)
        
        # Should ignore all invalid patterns
        assert len(variables) == 0
    
    def test_parse_template_variables_mixed_patterns(self):
        """Test parsing with mix of valid and invalid patterns"""
        content = "Valid: {{LIMITLESS_DAY}} Invalid: {{BADFORMAT}} Valid: {{NEWS_WEEK}}"
        
        variables = self.processor.parse_template_variables(content)
        
        # Should only find valid patterns
        assert len(variables) == 2
        assert variables[0].full_match == '{{LIMITLESS_DAY}}'
        assert variables[1].full_match == '{{NEWS_WEEK}}'
    
    def test_calculate_date_range_day(self):
        """Test date range calculation for DAY time range"""
        target_date = '2024-01-15'
        
        start_date, end_date = self.processor._calculate_date_range('DAY', target_date)
        
        assert start_date == '2024-01-15'
        assert end_date == '2024-01-15'
    
    def test_calculate_date_range_week(self):
        """Test date range calculation for WEEK time range"""
        target_date = '2024-01-15'  # Monday
        
        start_date, end_date = self.processor._calculate_date_range('WEEK', target_date)
        
        # Week = 7 days (today + 6 days prior)
        assert start_date == '2024-01-09'  # 6 days before Monday
        assert end_date == '2024-01-15'
    
    def test_calculate_date_range_month(self):
        """Test date range calculation for MONTH time range"""
        target_date = '2024-01-15'
        
        start_date, end_date = self.processor._calculate_date_range('MONTH', target_date)
        
        # Month = from 1st to target date
        assert start_date == '2024-01-01'
        assert end_date == '2024-01-15'
    
    def test_format_data_items_with_data(self):
        """Test formatting of data items when data exists"""
        variable = TemplateVariable(
            original_text='{{LIMITLESS_DAY}}',
            source='LIMITLESS',
            time_range='DAY',
            full_match='{{LIMITLESS_DAY}}'
        )
        
        formatted = self.processor._format_data_items(self.sample_data_items[:1], variable)
        
        assert '[2024-01-15] Sample limitless content for today' in formatted
        assert len(formatted) > 0
    
    def test_format_data_items_no_data(self):
        """Test formatting when no data items exist"""
        variable = TemplateVariable(
            original_text='{{LIMITLESS_DAY}}',
            source='LIMITLESS',
            time_range='DAY',
            full_match='{{LIMITLESS_DAY}}'
        )
        
        formatted = self.processor._format_data_items([], variable)
        
        assert formatted == '[No data available for LIMITLESS_DAY]'
    
    def test_format_data_items_truncation(self):
        """Test that very long content gets truncated"""
        long_content_item = {
            'content': 'x' * 1000,  # Very long content
            'days_date': '2024-01-15'
        }
        
        variable = TemplateVariable(
            original_text='{{LIMITLESS_DAY}}',
            source='LIMITLESS',
            time_range='DAY', 
            full_match='{{LIMITLESS_DAY}}'
        )
        
        formatted = self.processor._format_data_items([long_content_item], variable)
        
        # Should be truncated
        assert '...' in formatted
        assert len(formatted) < 1000
    
    def test_get_namespace_for_source(self):
        """Test mapping of template sources to database namespaces"""
        assert self.processor._get_namespace_for_source('LIMITLESS') == 'limitless'
        assert self.processor._get_namespace_for_source('TWITTER') == 'twitter'
        assert self.processor._get_namespace_for_source('NEWS') == 'news'
        assert self.processor._get_namespace_for_source('INVALID') is None
    
    @patch('services.template_processor.datetime')
    def test_get_current_date(self, mock_datetime):
        """Test getting current date in configured timezone"""
        # Mock datetime to return a specific date
        mock_now = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        mock_datetime.now.return_value = mock_now
        
        current_date = self.processor._get_current_date()
        
        assert current_date == '2024-01-15'
    
    def test_resolve_template_with_valid_variables(self):
        """Test resolving template with valid variables"""
        content = "Today's data: {{LIMITLESS_DAY}}"
        target_date = '2024-01-15'
        
        result = self.processor.resolve_template(content, target_date)
        
        assert result.original_content == content
        assert result.variables_resolved == 1
        assert len(result.errors) == 0
        assert 'Sample limitless content for today' in result.resolved_content
        assert '{{LIMITLESS_DAY}}' not in result.resolved_content
    
    def test_resolve_template_with_invalid_variables(self):
        """Test resolving template with invalid variables"""
        content = "Invalid: {{INVALID_SOURCE}}"
        target_date = '2024-01-15'
        
        result = self.processor.resolve_template(content, target_date)
        
        assert result.original_content == content
        assert result.variables_resolved == 0
        # Invalid variables should remain unchanged
        assert '{{INVALID_SOURCE}}' in result.resolved_content
    
    def test_resolve_template_mixed_valid_invalid(self):
        """Test resolving template with mix of valid and invalid variables"""
        content = "Valid: {{LIMITLESS_DAY}} Invalid: {{BAD_FORMAT}}"
        target_date = '2024-01-15'
        
        result = self.processor.resolve_template(content, target_date)
        
        assert result.variables_resolved == 1
        assert 'Sample limitless content for today' in result.resolved_content
        assert '{{LIMITLESS_DAY}}' not in result.resolved_content
        assert '{{BAD_FORMAT}}' in result.resolved_content  # Invalid remains
    
    def test_resolve_template_no_data(self):
        """Test resolving template when no data exists for date"""
        content = "Data: {{LIMITLESS_DAY}}"
        target_date = '2024-01-16'  # Date with no data
        
        result = self.processor.resolve_template(content, target_date)
        
        assert result.variables_resolved == 1
        assert '[No data available for LIMITLESS_DAY]' in result.resolved_content
    
    def test_resolve_template_default_date(self):
        """Test resolving template with default (current) date"""
        content = "Data: {{LIMITLESS_DAY}}"
        
        with patch.object(self.processor, '_get_current_date', return_value='2024-01-15'):
            result = self.processor.resolve_template(content)
        
        assert result.variables_resolved == 1
        assert 'Sample limitless content for today' in result.resolved_content
    
    def test_validate_template_all_valid(self):
        """Test template validation with all valid variables"""
        content = "{{LIMITLESS_DAY}} {{TWITTER_WEEK}} {{NEWS_MONTH}}"
        
        validation = self.processor.validate_template(content)
        
        assert validation['is_valid'] is True
        assert validation['total_variables'] == 3
        assert len(validation['valid_variables']) == 3
        assert len(validation['invalid_variables']) == 0
        assert 'LIMITLESS' in validation['supported_sources']
        assert 'DAY' in validation['supported_time_ranges']
    
    def test_validate_template_some_invalid(self):
        """Test template validation with some invalid variables"""
        content = "{{LIMITLESS_DAY}} {{INVALID_SOURCE}} {{NEWS_BADRANGE}}"
        
        validation = self.processor.validate_template(content)
        
        assert validation['is_valid'] is False
        assert validation['total_variables'] == 1  # Only valid ones counted
        assert len(validation['valid_variables']) == 1
        assert validation['valid_variables'][0] == '{{LIMITLESS_DAY}}'
    
    def test_validate_template_no_variables(self):
        """Test template validation with no template variables"""
        content = "This is plain text with no templates"
        
        validation = self.processor.validate_template(content)
        
        assert validation['is_valid'] is True
        assert validation['total_variables'] == 0
        assert len(validation['valid_variables']) == 0
        assert len(validation['invalid_variables']) == 0
    
    def test_add_source_extensibility(self):
        """Test adding new data sources for extensibility"""
        # Add new source
        self.processor.add_source('custom_namespace', 'CUSTOM')
        
        # Verify it was added
        sources = self.processor.get_supported_sources()
        assert 'custom_namespace' in sources
        assert sources['custom_namespace'] == 'CUSTOM'
        
        # Verify it's now recognized in validation
        content = "{{CUSTOM_DAY}}"
        validation = self.processor.validate_template(content)
        assert validation['is_valid'] is True
        assert 'CUSTOM' in validation['supported_sources']


class TestTemplateProcessorCaching:
    """Test suite for template caching functionality"""
    
    def setup_method(self):
        """Set up test fixtures for caching tests"""
        self.db_service = DatabaseService(":memory:")
        self.mock_config = Mock(spec=AppConfig)
        
        # Add test data
        self.db_service.store_data_item(
            id='limitless:test',
            namespace='limitless',
            source_id='test',
            content='Test content',
            days_date='2024-01-15'
        )
        
        # Initialize processor with caching enabled
        self.processor = TemplateProcessor(
            database=self.db_service,
            config=self.mock_config,
            timezone='UTC',
            cache_enabled=True,
            cache_ttl_hours=1
        )
        
        # Create template cache table (migration would normally do this)
        self._create_template_cache_table()
    
    def _create_template_cache_table(self):
        """Create template cache table for testing"""
        with self.db_service.get_connection() as conn:
            conn.execute("""
                CREATE TABLE template_cache (
                    id TEXT PRIMARY KEY,
                    template_hash TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    target_date TEXT NOT NULL,
                    resolved_content TEXT NOT NULL,
                    variables_resolved INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            conn.commit()
    
    def test_cache_hit(self):
        """Test cache hit scenario"""
        content = "Test: {{LIMITLESS_DAY}}"
        target_date = '2024-01-15'
        
        # First call should resolve and cache
        result1 = self.processor.resolve_template(content, target_date)
        assert result1.variables_resolved == 1
        
        # Second call should hit cache
        with patch.object(self.processor, '_resolve_variable') as mock_resolve:
            result2 = self.processor.resolve_template(content, target_date)
            
            # Should not call _resolve_variable due to cache hit
            mock_resolve.assert_not_called()
            assert result2.resolved_content == result1.resolved_content
    
    def test_cache_miss_different_content(self):
        """Test cache miss with different content"""
        target_date = '2024-01-15'
        
        # First call
        result1 = self.processor.resolve_template("{{LIMITLESS_DAY}}", target_date)
        
        # Different content should miss cache
        result2 = self.processor.resolve_template("{{LIMITLESS_WEEK}}", target_date)
        
        assert result1.resolved_content != result2.resolved_content
    
    def test_cache_miss_different_date(self):
        """Test cache miss with different target date"""
        content = "{{LIMITLESS_DAY}}"
        
        # First call
        result1 = self.processor.resolve_template(content, '2024-01-15')
        
        # Different date should miss cache
        result2 = self.processor.resolve_template(content, '2024-01-16')
        
        # Results should be different (even if no data for second date)
        assert result1.resolved_content != result2.resolved_content
    
    def test_cache_expiration(self):
        """Test that expired cache entries are not used"""
        content = "{{LIMITLESS_DAY}}"
        target_date = '2024-01-15'
        
        # First resolution
        result1 = self.processor.resolve_template(content, target_date)
        
        # Manually expire the cache entry
        template_hash = self.processor._generate_template_hash(content, target_date)
        with self.db_service.get_connection() as conn:
            conn.execute("""
                UPDATE template_cache 
                SET expires_at = datetime('now', '-1 hour')
                WHERE template_hash = ?
            """, (template_hash,))
            conn.commit()
        
        # Should resolve again (cache miss due to expiration)
        with patch.object(self.processor, '_resolve_variable') as mock_resolve:
            mock_resolve.return_value = "Fresh data"
            result2 = self.processor.resolve_template(content, target_date)
            
            # Should call _resolve_variable due to expired cache
            mock_resolve.assert_called()
    
    def test_cache_disabled(self):
        """Test that caching can be disabled"""
        processor_no_cache = TemplateProcessor(
            database=self.db_service,
            config=self.mock_config,
            cache_enabled=False
        )
        
        content = "{{LIMITLESS_DAY}}"
        target_date = '2024-01-15'
        
        # Both calls should resolve (no caching)
        with patch.object(processor_no_cache, '_resolve_variable') as mock_resolve:
            mock_resolve.return_value = "Test data"
            
            processor_no_cache.resolve_template(content, target_date)
            processor_no_cache.resolve_template(content, target_date)
            
            # Should be called twice (no caching)
            assert mock_resolve.call_count == 2
    
    def test_cache_cleanup(self):
        """Test cleanup of expired cache entries"""
        # Add some expired entries manually
        with self.db_service.get_connection() as conn:
            expired_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
            
            conn.execute("""
                INSERT INTO template_cache 
                (id, template_hash, content_hash, target_date, resolved_content, 
                 variables_resolved, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ('expired1', 'hash1', 'content1', '2024-01-01', 'old data', 1, expired_time))
            
            conn.execute("""
                INSERT INTO template_cache 
                (id, template_hash, content_hash, target_date, resolved_content, 
                 variables_resolved, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, ('expired2', 'hash2', 'content2', '2024-01-02', 'old data', 1, expired_time))
            
            conn.commit()
        
        # Call cleanup
        self.processor._cleanup_expired_cache()
        
        # Verify entries were removed
        with self.db_service.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM template_cache")
            count = cursor.fetchone()['count']
            assert count == 0


class TestTemplateProcessorIntegration:
    """Integration tests for TemplateProcessor with real data scenarios"""
    
    def setup_method(self):
        """Set up integration test fixtures"""
        self.db_service = DatabaseService(":memory:")
        self.mock_config = Mock(spec=AppConfig)
        
        # Add realistic test data spanning multiple days
        test_data = [
            # Limitless data
            ('limitless:meeting1', 'limitless', 'meeting1', 'Team standup meeting', '2024-01-15'),
            ('limitless:meeting2', 'limitless', 'meeting2', 'Client review call', '2024-01-14'), 
            ('limitless:meeting3', 'limitless', 'meeting3', 'Project planning session', '2024-01-13'),
            
            # Twitter data
            ('twitter:tweet1', 'twitter', 'tweet1', 'Interesting article about AI', '2024-01-15'),
            ('twitter:tweet2', 'twitter', 'tweet2', 'New product launch announcement', '2024-01-14'),
            
            # News data
            ('news:article1', 'news', 'article1', 'Breaking: Tech industry update', '2024-01-15'),
            ('news:article2', 'news', 'article2', 'Market analysis report', '2024-01-10'),
        ]
        
        for item_id, namespace, source_id, content, days_date in test_data:
            self.db_service.store_data_item(
                id=item_id,
                namespace=namespace,
                source_id=source_id,
                content=content,
                days_date=days_date
            )
        
        self.processor = TemplateProcessor(
            database=self.db_service,
            config=self.mock_config,
            timezone='UTC'
        )
    
    def test_complex_template_resolution(self):
        """Test resolving a complex template with multiple variables"""
        template = """
        Daily Summary for {{LIMITLESS_DAY}}
        
        Recent Activity:
        {{LIMITLESS_WEEK}}
        
        Social Media:
        {{TWITTER_DAY}}
        
        News This Month:
        {{NEWS_MONTH}}
        """
        
        result = self.processor.resolve_template(template, '2024-01-15')
        
        # Should resolve all variables
        assert result.variables_resolved == 4
        assert len(result.errors) == 0
        
        # Check that template variables were replaced
        assert '{{LIMITLESS_DAY}}' not in result.resolved_content
        assert '{{LIMITLESS_WEEK}}' not in result.resolved_content
        assert '{{TWITTER_DAY}}' not in result.resolved_content
        assert '{{NEWS_MONTH}}' not in result.resolved_content
        
        # Check that actual data is present
        assert 'Team standup meeting' in result.resolved_content
        assert 'Interesting article about AI' in result.resolved_content
        assert 'Breaking: Tech industry update' in result.resolved_content
    
    def test_week_range_includes_multiple_days(self):
        """Test that WEEK range includes data from multiple days"""
        template = "Weekly summary: {{LIMITLESS_WEEK}}"
        
        result = self.processor.resolve_template(template, '2024-01-15')
        
        # Should include data from multiple days in the week
        resolved = result.resolved_content
        assert 'Team standup meeting' in resolved  # 2024-01-15
        assert 'Client review call' in resolved     # 2024-01-14  
        assert 'Project planning session' in resolved  # 2024-01-13
    
    def test_month_range_includes_all_month_data(self):
        """Test that MONTH range includes all data from start of month"""
        template = "Monthly news: {{NEWS_MONTH}}"
        
        result = self.processor.resolve_template(template, '2024-01-15')
        
        resolved = result.resolved_content
        # Should include both January articles
        assert 'Breaking: Tech industry update' in resolved  # 2024-01-15
        assert 'Market analysis report' in resolved          # 2024-01-10
    
    def test_error_handling_with_partial_failures(self):
        """Test handling when some variables fail to resolve"""
        # Create scenario where database might fail for some queries
        with patch.object(self.db_service, 'get_data_items_by_date') as mock_get_data:
            # First call succeeds, second call fails
            mock_get_data.side_effect = [
                [{'content': 'Success data', 'days_date': '2024-01-15'}],
                Exception("Database error")
            ]
            
            template = "Good: {{LIMITLESS_DAY}} Bad: {{TWITTER_DAY}}"
            result = self.processor.resolve_template(template, '2024-01-15')
            
            # Should have one success and one error
            assert result.variables_resolved == 1
            assert len(result.errors) == 1
            
            # Successful variable should be resolved
            assert 'Success data' in result.resolved_content
            # Failed variable should have error placeholder
            assert '[Error resolving {{TWITTER_DAY}}]' in result.resolved_content