import json
import asyncio
import logging
from typing import List, Dict, Optional
import openai
import anthropic
from config.models import LLMConfig


logger = logging.getLogger(__name__)


class NamespacePredictionService:
    """LLM-powered service for predicting relevant namespaces for queries"""
    
    def __init__(self, llm_config: LLMConfig, available_namespaces: List[str]):
        self.llm_config = llm_config
        self.available_namespaces = available_namespaces
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the appropriate LLM client"""
        try:
            if self.llm_config.provider == "openai":
                self.client = openai.OpenAI(api_key=self.llm_config.api_key)
            elif self.llm_config.provider == "anthropic":
                self.client = anthropic.Anthropic(api_key=self.llm_config.api_key)
            else:
                raise ValueError(f"Unsupported LLM provider: {self.llm_config.provider}")
            
            logger.info(f"Initialized {self.llm_config.provider} client for namespace prediction")
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise
    
    async def predict_namespaces(self, query: str, max_retries: int = None) -> Dict[str, List[str]]:
        """
        Predict relevant namespaces with priority for query
        
        Args:
            query: User query text
            max_retries: Maximum retry attempts (defaults to config value)
            
        Returns:
            Dictionary with 'namespaces' and 'priority' lists
        """
        if max_retries is None:
            max_retries = getattr(self.llm_config, 'max_retries', 3)
        
        if not self.available_namespaces:
            return {"namespaces": [], "priority": []}
        
        prompt = self._build_prediction_prompt(query)
        
        for attempt in range(max_retries):
            try:
                response = await self._call_llm(prompt)
                return self._parse_response(response)
                
            except Exception as e:
                logger.warning(f"Namespace prediction attempt {attempt + 1} failed: {e}")
                
                if attempt == max_retries - 1:
                    # Final fallback: return all namespaces
                    logger.error("All namespace prediction attempts failed, using fallback")
                    return {
                        "namespaces": self.available_namespaces,
                        "priority": self.available_namespaces
                    }
                
                # Exponential backoff
                await asyncio.sleep(0.1 * (2 ** attempt))
        
        # Should never reach here, but safety fallback
        return {
            "namespaces": self.available_namespaces,
            "priority": self.available_namespaces
        }
    
    def _build_prediction_prompt(self, query: str) -> str:
        """Build the prompt for namespace prediction"""
        namespaces_str = ", ".join(self.available_namespaces)
        
        return f"""Given this user query: "{query}"

Available data sources: {namespaces_str}

Determine which sources are most relevant for answering this query. Consider:
- Keywords in the query that might relate to specific data sources
- The type of information the user is seeking
- The likely content of each data source

Return a JSON response with:
- "namespaces": list of relevant source names (subset of available sources)
- "priority": same sources ordered by importance for this query (most important first)

If no sources seem particularly relevant, include all sources.
If the query is very specific to one domain, you may return just 1-2 sources.

Example response: {{"namespaces": ["limitless", "documents"], "priority": ["limitless", "documents"]}}

Response:"""
    
    async def _call_llm(self, prompt: str) -> str:
        """Make LLM API call"""
        try:
            if self.llm_config.provider == "openai":
                response = await self._call_openai(prompt)
            elif self.llm_config.provider == "anthropic":
                response = await self._call_anthropic(prompt)
            else:
                raise ValueError(f"Unsupported provider: {self.llm_config.provider}")
            
            return response
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise
    
    async def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.llm_config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.llm_config.temperature,
                max_tokens=self.llm_config.max_tokens,
                timeout=self.llm_config.timeout
            )
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise
    
    async def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API"""
        try:
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.llm_config.model,
                max_tokens=self.llm_config.max_tokens,
                temperature=self.llm_config.temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text
            
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}")
            raise
    
    def _parse_response(self, response: str) -> Dict[str, List[str]]:
        """Parse LLM response into structured format"""
        try:
            # Try to extract JSON from response
            response_clean = response.strip()
            
            # Handle cases where LLM adds extra text around JSON
            start_idx = response_clean.find('{')
            end_idx = response_clean.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_clean[start_idx:end_idx]
                parsed = json.loads(json_str)
            else:
                # Try parsing the whole response
                parsed = json.loads(response_clean)
            
            # Validate response structure
            if not isinstance(parsed, dict):
                raise ValueError("Response is not a dictionary")
            
            namespaces = parsed.get("namespaces", [])
            priority = parsed.get("priority", [])
            
            if not isinstance(namespaces, list) or not isinstance(priority, list):
                raise ValueError("namespaces and priority must be lists")
            
            # Filter to only available namespaces
            valid_namespaces = [ns for ns in namespaces if ns in self.available_namespaces]
            valid_priority = [ns for ns in priority if ns in self.available_namespaces]
            
            # Ensure we have at least some namespaces
            if not valid_namespaces:
                valid_namespaces = self.available_namespaces
            if not valid_priority:
                valid_priority = self.available_namespaces
            
            return {
                "namespaces": valid_namespaces,
                "priority": valid_priority
            }
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse LLM response: {e}. Response: {response[:200]}...")
            
            # Fallback: try to extract namespace names from text
            fallback_namespaces = self._extract_namespaces_from_text(response)
            if fallback_namespaces:
                return {
                    "namespaces": fallback_namespaces,
                    "priority": fallback_namespaces
                }
            
            # Final fallback: all namespaces
            return {
                "namespaces": self.available_namespaces,
                "priority": self.available_namespaces
            }
    
    def _extract_namespaces_from_text(self, text: str) -> List[str]:
        """Extract namespace names from free text response"""
        found_namespaces = []
        text_lower = text.lower()
        
        for namespace in self.available_namespaces:
            if namespace.lower() in text_lower:
                found_namespaces.append(namespace)
        
        return found_namespaces
    
    def update_available_namespaces(self, namespaces: List[str]):
        """Update the list of available namespaces"""
        self.available_namespaces = namespaces
        logger.info(f"Updated available namespaces: {namespaces}")
    
    def get_config_info(self) -> Dict[str, any]:
        """Get configuration information"""
        return {
            'provider': self.llm_config.provider,
            'model': self.llm_config.model,
            'temperature': self.llm_config.temperature,
            'max_tokens': self.llm_config.max_tokens,
            'available_namespaces': self.available_namespaces,
            'namespace_count': len(self.available_namespaces)
        }
    
    async def test_prediction(self, test_query: str = "What did I do yesterday?") -> Dict[str, any]:
        """Test the prediction service with a sample query"""
        try:
            start_time = asyncio.get_event_loop().time()
            result = await self.predict_namespaces(test_query)
            end_time = asyncio.get_event_loop().time()
            
            return {
                'success': True,
                'query': test_query,
                'result': result,
                'response_time_seconds': end_time - start_time,
                'namespaces_returned': len(result.get('namespaces', [])),
                'priority_returned': len(result.get('priority', []))
            }
            
        except Exception as e:
            return {
                'success': False,
                'query': test_query,
                'error': str(e),
                'response_time_seconds': 0,
                'namespaces_returned': 0,
                'priority_returned': 0
            }


class MockNamespacePredictionService:
    """Mock implementation for testing without LLM calls"""
    
    def __init__(self, available_namespaces: List[str]):
        self.available_namespaces = available_namespaces
    
    async def predict_namespaces(self, query: str, max_retries: int = None) -> Dict[str, List[str]]:
        """Mock prediction that returns all namespaces"""
        # Simple mock logic - could be enhanced with keyword matching
        return {
            "namespaces": self.available_namespaces,
            "priority": self.available_namespaces
        }
    
    def update_available_namespaces(self, namespaces: List[str]):
        self.available_namespaces = namespaces
    
    def get_config_info(self) -> Dict[str, any]:
        return {
            'provider': 'mock',
            'model': 'mock',
            'available_namespaces': self.available_namespaces,
            'namespace_count': len(self.available_namespaces)
        }
    
    async def test_prediction(self, test_query: str = "test") -> Dict[str, any]:
        result = await self.predict_namespaces(test_query)
        return {
            'success': True,
            'query': test_query,
            'result': result,
            'response_time_seconds': 0.001,
            'namespaces_returned': len(result.get('namespaces', [])),
            'priority_returned': len(result.get('priority', []))
        }