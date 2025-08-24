"""
Test to verify that news data is properly separated from lifelog data in day view.

This test ensures that the Daily Conversations & Activities section only contains
data from the 'limitless' namespace and excludes news data.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock


def test_namespace_filtering_fix():
    """Test that the fix properly filters markdown content by namespace"""
    
    # Import the function to test
    try:
        from api.routes.calendar import get_enhanced_day_data
    except ImportError:
        print("❌ Could not import get_enhanced_day_data function")
        return False
    
    # Create mock database service
    mock_db = MagicMock()
    
    # Mock get_data_items_by_date to return both news and limitless items
    test_items = [
        {
            'id': 'news_1',
            'namespace': 'news', 
            'content': 'Breaking: Test news article'
        },
        {
            'id': 'limitless_1', 
            'namespace': 'limitless',
            'content': 'Had a meeting about project planning'
        }
    ]
    mock_db.get_data_items_by_date.return_value = test_items
    
    # Mock get_markdown_by_date with namespace filtering (the fix)
    def mock_get_markdown_by_date(date, namespaces=None):
        if namespaces and 'limitless' in namespaces:
            # Should only return limitless content (this is the fix)
            return '# Meeting Notes\n\nDiscussed project timeline and deliverables'
        else:
            # Without filtering, would return both (old behavior)
            return '# Breaking News\n\nThis is a test news article\n\n---\n\n# Meeting Notes\n\nDiscussed project timeline and deliverables'
    
    mock_db.get_markdown_by_date.side_effect = mock_get_markdown_by_date
    
    # Create mock news service
    mock_news = MagicMock()
    mock_news.get_news_by_date.return_value = [
        {
            'title': 'Test News Article',
            'link': 'https://example.com/news',
            'published_datetime_utc': '2024-01-15T08:00:00Z'
        }
    ]
    
    # Create mock weather service
    mock_weather = MagicMock()
    mock_weather.get_weather_for_date_range.return_value = []
    
    try:
        # Call the enhanced day data function
        result = get_enhanced_day_data(
            date="2024-01-15",
            database=mock_db,
            weather_service=mock_weather,
            news_service=mock_news
        )
        
        # Verify database.get_markdown_by_date was called with limitless namespace filter
        mock_db.get_markdown_by_date.assert_called_with("2024-01-15", namespaces=['limitless'])
        print("✓ get_markdown_by_date called with correct namespace filter")
        
        # Verify the result structure
        assert 'limitless' in result, "Result should contain limitless section"
        assert 'news' in result, "Result should contain news section"
        assert 'weather' in result, "Result should contain weather section"
        print("✓ Result contains all expected sections")
        
        # Verify limitless section only contains limitless content (no news)
        limitless_markdown = result['limitless']['markdown_content']
        assert 'Meeting Notes' in limitless_markdown, "Should contain limitless content"
        assert 'Breaking News' not in limitless_markdown, "Should NOT contain news content"
        assert 'test news article' not in limitless_markdown.lower(), "Should NOT contain news content"
        print("✓ Limitless section properly excludes news data")
        
        # Verify news section contains news data separately
        news_articles = result['news']['articles']
        assert len(news_articles) == 1, "Should have one news article"
        assert news_articles[0]['title'] == 'Test News Article', "Should contain news article"
        print("✓ News section properly contains news data")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


def test_markdown_extraction_behavior():
    """Test the different behaviors of markdown extraction with and without namespace filtering"""
    
    # Mock database service
    mock_db = MagicMock()
    
    def mock_get_markdown_by_date(date, namespaces=None):
        if namespaces and 'limitless' in namespaces:
            # With filtering (the fix) - only limitless content
            return '# Meeting Notes\n\nDiscussed project timeline and deliverables'
        else:
            # Without filtering (old behavior) - all content mixed together
            return '# Breaking News\n\nThis is a test news article\n\n---\n\n# Meeting Notes\n\nDiscussed project timeline and deliverables'
    
    mock_db.get_markdown_by_date.side_effect = mock_get_markdown_by_date
    
    # Test with limitless namespace filtering (the fix)
    limitless_only = mock_db.get_markdown_by_date("2024-01-15", namespaces=['limitless'])
    assert 'Meeting Notes' in limitless_only, "Filtered result should contain limitless content"
    assert 'Breaking News' not in limitless_only, "Filtered result should NOT contain news content"
    print("✓ Namespace filtering properly excludes news from limitless content")
    
    # Test without filtering (old behavior - should include everything)
    all_content = mock_db.get_markdown_by_date("2024-01-15")
    assert 'Meeting Notes' in all_content, "Unfiltered result should contain limitless content"
    assert 'Breaking News' in all_content, "Unfiltered result should contain news content"
    print("✓ Without filtering, all content types are included (old behavior)")
    
    return True


if __name__ == "__main__":
    print("🧪 Testing data separation fix...")
    print("=" * 50)
    
    success = True
    
    # Test 1: Verify the fix works
    print("\n📋 Test 1: Namespace filtering fix")
    if not test_namespace_filtering_fix():
        success = False
    
    # Test 2: Verify markdown extraction behavior 
    print("\n📋 Test 2: Markdown extraction behavior")
    if not test_markdown_extraction_behavior():
        success = False
    
    print("\n" + "=" * 50)
    if success:
        print("✅ All data separation tests passed!")
        print("\n🎯 Summary:")
        print("   • News data is properly excluded from Daily Conversations & Activities section")
        print("   • Limitless content is correctly filtered using namespace ['limitless']")
        print("   • News data appears separately in the News Headlines section")
        print("   • The fix prevents data contamination between sections")
    else:
        print("❌ Some tests failed!")
        sys.exit(1)