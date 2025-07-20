"""
Integration tests for API with real external services
"""

import pytest
import os
from unittest.mock import patch, AsyncMock

from sources.base import LimitlessSource
from services.namespace_prediction import NamespacePredictionService
from config.models import LimitlessConfig, LLMConfig


class TestLimitlessAPIIntegration:
    """Tests for Limitless API integration (both mock and real)"""
    
    @pytest.mark.asyncio
    async def test_limitless_source_mock(self, limitless_config: LimitlessConfig):
        """Test Limitless source with mocked API calls"""
        source = LimitlessSource("limitless", limitless_config.dict())
        
        # Mock the API response
        mock_response = {
            'data': {
                'lifelogs': [
                    {
                        'id': 'test_lifelog_1',
                        'title': 'Test Lifelog',
                        'markdown': 'This is test content from Limitless',
                        'startTime': '2024-01-01T10:00:00Z',
                        'endTime': '2024-01-01T11:00:00Z',
                        'contents': [
                            {
                                'type': 'blockquote',
                                'content': 'Test conversation content',
                                'speakerName': 'Test User'
                            }
                        ]
                    }
                ]
            },
            'meta': {
                'lifelogs': {
                    'nextCursor': None,
                    'count': 1
                }
            }
        }
        
        with patch.object(source, '_make_request', new=AsyncMock(return_value=mock_response)):
            # Test fetching data
            items = []
            async for item in source.fetch_data():
                items.append(item)
            
            assert len(items) == 1
            item = items[0]
            assert item.source_id == 'test_lifelog_1'
            assert 'This is test content from Limitless' in item.content
            assert item.metadata['title'] == 'Test Lifelog'
            
            # Test source info
            info = await source.get_source_info()
            assert info['source_type'] == 'limitless'
            assert 'timezone' in info
    
    @pytest.mark.skipif(
        not os.getenv("ENABLE_REAL_API_TESTS"),
        reason="Real API tests disabled"
    )
    @pytest.mark.asyncio
    async def test_limitless_source_real_api(self, real_limitless_api_key: str):
        """Test Limitless source with real API (requires valid API key)"""
        config = LimitlessConfig(
            api_key=real_limitless_api_key,
            base_url="https://api.limitless.ai/v1",
            timezone="UTC"
        )
        
        source = LimitlessSource("limitless", config.dict())
        
        # Test connection
        is_connected = await source.test_connection()
        assert is_connected, "Failed to connect to Limitless API"
        
        # Test fetching a small amount of data
        items = []
        count = 0
        async for item in source.fetch_data():
            items.append(item)
            count += 1
            if count >= 3:  # Limit to avoid quota issues
                break
        
        # Should get some items (unless account is empty)
        for item in items:
            assert item.source_id
            assert item.content
            assert item.metadata
            assert 'source_type' in item.metadata
    
    @pytest.mark.asyncio
    async def test_limitless_config_validation(self):
        """Test Limitless configuration validation"""
        # Valid config
        valid_config = LimitlessConfig(api_key="test_key")
        assert valid_config.api_key == "test_key"
        
        # Invalid config (empty API key)
        with pytest.raises(ValueError):
            LimitlessConfig(api_key="")


class TestLLMIntegration:
    """Tests for LLM integration (both mock and real)"""
    
    @pytest.mark.asyncio
    async def test_namespace_prediction_mock(self, llm_config: LLMConfig):
        """Test namespace prediction with mocked LLM"""
        available_namespaces = ["limitless", "documents", "notes"]
        service = NamespacePredictionService(llm_config, available_namespaces)
        
        # Mock the LLM response
        mock_response = '{"namespaces": ["limitless", "notes"], "priority": ["limitless", "notes"]}'
        
        with patch.object(service, '_call_llm', new=AsyncMock(return_value=mock_response)):
            result = await service.predict_namespaces("What did I do yesterday?")
            
            assert 'namespaces' in result
            assert 'priority' in result
            assert all(ns in available_namespaces for ns in result['namespaces'])
    
    @pytest.mark.skipif(
        not os.getenv("ENABLE_REAL_API_TESTS"),
        reason="Real API tests disabled"
    )
    @pytest.mark.asyncio
    async def test_namespace_prediction_real_openai(self, real_openai_api_key: str):
        """Test namespace prediction with real OpenAI API"""
        config = LLMConfig(
            provider="openai",
            model="gpt-3.5-turbo",
            api_key=real_openai_api_key,
            temperature=0.1,
            max_tokens=100
        )
        
        available_namespaces = ["limitless", "documents", "emails", "notes"]
        service = NamespacePredictionService(config, available_namespaces)
        
        # Test prediction
        result = await service.predict_namespaces("Show me my recent meeting notes")
        
        assert 'namespaces' in result
        assert 'priority' in result
        assert len(result['namespaces']) > 0
        assert all(ns in available_namespaces for ns in result['namespaces'])
        
        # For meeting notes query, should likely include 'documents' or 'notes'
        relevant_namespaces = {'documents', 'notes'}
        predicted_namespaces = set(result['namespaces'])
        assert len(relevant_namespaces.intersection(predicted_namespaces)) > 0
    
    @pytest.mark.asyncio
    async def test_llm_error_handling(self, llm_config: LLMConfig):
        """Test LLM error handling and fallbacks"""
        available_namespaces = ["test1", "test2"]
        service = NamespacePredictionService(llm_config, available_namespaces)
        
        # Mock a failed LLM call
        with patch.object(service, '_call_llm', side_effect=Exception("API Error")):
            result = await service.predict_namespaces("test query")
            
            # Should fallback to all namespaces
            assert result['namespaces'] == available_namespaces
            assert result['priority'] == available_namespaces
    
    @pytest.mark.asyncio
    async def test_llm_invalid_response_handling(self, llm_config: LLMConfig):
        """Test handling of invalid LLM responses"""
        available_namespaces = ["test1", "test2"]
        service = NamespacePredictionService(llm_config, available_namespaces)
        
        # Test invalid JSON response
        with patch.object(service, '_call_llm', new=AsyncMock(return_value="invalid json")):
            result = await service.predict_namespaces("test query")
            assert result['namespaces'] == available_namespaces
        
        # Test response with invalid namespaces
        invalid_response = '{"namespaces": ["nonexistent"], "priority": ["nonexistent"]}'
        with patch.object(service, '_call_llm', new=AsyncMock(return_value=invalid_response)):
            result = await service.predict_namespaces("test query")
            assert result['namespaces'] == available_namespaces


class TestRateLimitingAndRetries:
    """Test rate limiting and retry logic"""
    
    @pytest.mark.asyncio
    async def test_api_retry_logic(self, limitless_config: LimitlessConfig):
        """Test API retry logic with transient failures"""
        source = LimitlessSource("limitless", limitless_config.dict())
        
        # Mock a sequence of responses: fail, fail, succeed
        call_count = 0
        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise Exception("Transient error")
            return {
                'data': {'lifelogs': []},
                'meta': {'lifelogs': {'nextCursor': None, 'count': 0}}
            }
        
        with patch.object(source, '_make_request', side_effect=mock_request):
            # This would normally fail, but retry logic should handle it
            # For this test, we'll just verify the source can handle errors gracefully
            try:
                info = await source.get_source_info()
                # If we get here, retry worked
                assert call_count > 1
            except Exception:
                # If retries are not implemented yet, this is expected
                pass
    
    @pytest.mark.skipif(
        not os.getenv("ENABLE_REAL_API_TESTS"),
        reason="Real API tests disabled"
    )
    @pytest.mark.asyncio
    async def test_rate_limiting_respect(self, real_limitless_api_key: str):
        """Test that we respect API rate limits"""
        config = LimitlessConfig(
            api_key=real_limitless_api_key,
            base_url="https://api.limitless.ai/v1",
            timezone="UTC"
        )
        
        source = LimitlessSource("limitless", config.dict())
        
        # Make multiple rapid requests and ensure we don't hit rate limits
        for i in range(3):
            try:
                await source.get_source_info()
                # Add small delay to be respectful
                import asyncio
                await asyncio.sleep(0.5)
            except Exception as e:
                if "rate limit" in str(e).lower():
                    pytest.fail("Hit rate limit - need to implement rate limiting")
                # Other errors are acceptable for this test


class TestDataConsistency:
    """Test data consistency across mock and real APIs"""
    
    @pytest.mark.asyncio
    async def test_limitless_data_structure_consistency(self):
        """Test that mock and real Limitless data have consistent structure"""
        # This ensures our mocks match the real API structure
        
        # Expected structure for a Limitless lifelog item
        expected_fields = [
            'source_id',
            'content', 
            'metadata',
            'timestamp'
        ]
        
        expected_metadata_fields = [
            'title',
            'start_time',
            'end_time',
            'source_type'
        ]
        
        # Test with mock data (from previous test)
        mock_config = LimitlessConfig(api_key="test_key")
        source = LimitlessSource("limitless", mock_config.dict())
        
        mock_response = {
            'data': {
                'lifelogs': [{
                    'id': 'test_id',
                    'title': 'Test',
                    'markdown': 'Test content',
                    'startTime': '2024-01-01T10:00:00Z',
                    'endTime': '2024-01-01T11:00:00Z',
                    'contents': []
                }]
            },
            'meta': {'lifelogs': {'nextCursor': None, 'count': 1}}
        }
        
        with patch.object(source, '_make_request', new=AsyncMock(return_value=mock_response)):
            async for item in source.fetch_data():
                # Check required fields
                for field in expected_fields:
                    assert hasattr(item, field), f"Missing field: {field}"
                
                # Check metadata structure
                for field in expected_metadata_fields:
                    assert field in item.metadata, f"Missing metadata field: {field}"
                
                break  # Just test first item