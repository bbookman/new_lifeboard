"""
Mock LLM Provider for Testing

This module provides a mock LLM provider that can be used in tests
to simulate LLM responses without requiring actual LLM services.
"""

import asyncio
from typing import Dict, Any, Optional, List
from .base import BaseLLMProvider, LLMResponse
import logging

logger = logging.getLogger(__name__)


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for testing purposes"""
    
    def __init__(self):
        super().__init__(provider_name="mock")
        self._is_available = True
        self._response_delay = 0.1  # Simulate small delay
        self._default_response = "Mock LLM response generated for testing purposes."
        self._custom_responses: Dict[str, str] = {}
        
    async def is_available(self) -> bool:
        """Check if the mock provider is available"""
        return self._is_available
    
    async def generate_response(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate a mock response"""
        # Simulate processing delay
        await asyncio.sleep(self._response_delay)
        
        # Check if we have a custom response for this prompt
        response_content = self._custom_responses.get(prompt, self._default_response)
        
        # Create mock usage stats
        usage_stats = {
            "total_tokens": len(response_content.split()) + len(prompt.split()),
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(response_content.split())
        }
        
        return LLMResponse(
            content=response_content,
            model="mock-model-v1",
            provider="mock",
            usage=usage_stats
        )
    
    async def close(self) -> None:
        """Close the mock provider (no-op for mock)"""
        logger.debug("Mock LLM provider closed")
        pass
    
    # Test helper methods
    def set_available(self, available: bool):
        """Set availability status for testing"""
        self._is_available = available
    
    def set_response_delay(self, delay: float):
        """Set response delay for testing"""
        self._response_delay = delay
    
    def set_default_response(self, response: str):
        """Set default response content"""
        self._default_response = response
    
    def add_custom_response(self, prompt: str, response: str):
        """Add custom response for specific prompt"""
        self._custom_responses[prompt] = response
    
    def clear_custom_responses(self):
        """Clear all custom responses"""
        self._custom_responses.clear()
    
    def get_mock_daily_summary_response(self, date: str) -> str:
        """Get a realistic mock daily summary response"""
        return f"""# Daily Summary for {date}

**🚀 Technology & Innovation**
- Continued development on Lifeboard application
- Implemented LLM integration with daily summary generation
- Enhanced API testing with comprehensive TDD approach

**💼 Professional Activities**
- Completed backend API integration for LLM services
- Developed comprehensive test suite covering multiple scenarios
- Fixed dependency injection issues in FastAPI routes

**🌱 Personal Growth**
- Applied Test-Driven Development methodology effectively
- Improved understanding of service dependency management
- Enhanced debugging skills for complex integration issues

**🌤️ Environment & Context**
- Perfect development environment with all tools configured
- Smooth development flow with proper testing infrastructure
- High productivity levels throughout implementation

**🎯 Key Themes & Takeaways**
1. **Test-Driven Success**: TDD approach led to robust implementation
2. **Integration Mastery**: Successfully integrated complex LLM services
3. **Quality Focus**: Comprehensive testing ensures reliability
4. **Problem Solving**: Systematically resolved dependency injection issues

This was a highly productive development day with successful implementation of LLM-powered daily summaries using Test-Driven Development methodology."""
    
    def setup_realistic_responses(self):
        """Setup realistic responses for common test scenarios"""
        # Daily summary response
        self.add_custom_response(
            "generate_daily_summary", 
            self.get_mock_daily_summary_response("2024-01-15")
        )
        
        # No data response
        self.add_custom_response(
            "no_data_summary",
            """# Daily Summary for 2024-12-25

**📋 Data Summary**
No significant digital activities were recorded for this date. This appears to be a quiet day with minimal tracked interactions.

**🤔 Possible Reasons**
- Holiday or weekend with reduced digital activity
- Day spent offline or away from tracked devices
- System downtime or data collection issues

**💡 Suggestion**
This could be a great opportunity to reflect on offline activities, personal time, or simply enjoying a peaceful day away from digital distractions."""
        )