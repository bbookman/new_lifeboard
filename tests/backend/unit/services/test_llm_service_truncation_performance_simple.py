"""
Simplified performance test for LLM service truncation impact.

Tests the performance difference between truncated and untruncated content
by directly measuring the template processing and LLM generation steps.
"""

import asyncio
import random
import time
import statistics
import pytest
from typing import List, Dict, Any
import sqlite3

from services.llm_service import LLMService
from services.template_processor import TemplateProcessor
from core.repositories.llm_repository import LLMRepository
from core.database import DatabaseService
from config.factory import ConfigFactory


class SimpleTruncationTest:
    """Simplified test class for measuring truncation impact"""
    
    def __init__(self):
        self.config = ConfigFactory.create_config()
        self.database = DatabaseService(self.config.database.path)
        self.template_processor = None
        self.llm_repo = None
        
    async def setup(self):
        """Initialize services for testing"""
        from core.repositories.repository_factory import RepositoryFactory
        from core.vector_store import VectorStoreService
        from core.embeddings import EmbeddingService
        from services.document_service import DocumentService
        
        # Initialize dependencies
        repository_factory = RepositoryFactory(self.database)
        vector_store = VectorStoreService(self.config.vector_store)
        embedding_service = EmbeddingService(self.config.embeddings)
        
        # Initialize document service
        self.document_service = DocumentService(
            database=self.database,
            vector_store=vector_store,
            embedding_service=embedding_service,
            config=self.config
        )
        await self.document_service._initialize_service()
        
        # Initialize LLM service
        self.llm_service = LLMService(
            repository_factory=repository_factory,
            document_service=self.document_service,
            config=self.config
        )
        await self.llm_service._initialize_service()
        
        # Get direct access to components
        self.template_processor = TemplateProcessor(repository_factory, self.config)
        self.llm_repo = repository_factory.get_llm_repository()
        
    def get_dates_with_limitless_data(self, sample_size: int = 20) -> List[str]:
        """Get random sample of dates that have limitless data"""
        with self.database.get_connection() as conn:
            cursor = conn.execute("""
                SELECT DISTINCT days_date 
                FROM data_items 
                WHERE namespace='limitless' 
                ORDER BY days_date DESC
            """)
            all_dates = [row['days_date'] for row in cursor.fetchall()]
            
        return random.sample(all_dates, min(sample_size, len(all_dates)))
    
    def get_limitless_data_for_date(self, days_date: str) -> List[Dict[str, Any]]:
        """Get all limitless data for a specific date"""
        with self.database.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, namespace, source_id, content, metadata, days_date, created_at
                FROM data_items 
                WHERE namespace='limitless' AND days_date = ?
                ORDER BY created_at
            """, (days_date,))
            return [dict(row) for row in cursor.fetchall()]
    
    def format_data_with_truncation(self, data_items: List[Dict[str, Any]], enable_truncation: bool) -> str:
        """Format data items with optional truncation"""
        if not data_items:
            return ""
        
        formatted_items = []
        for item in data_items:
            content = item.get('content', '')
            days_date = item.get('days_date', '')
            
            # Apply truncation only if enabled
            if enable_truncation and len(content) > 500:
                content = content[:500] + "..."
            
            if days_date:
                formatted_items.append(f"[{days_date}] {content}")
            else:
                formatted_items.append(content)
        
        result = "\n".join(formatted_items)
        
        # Apply total output truncation only if enabled
        if enable_truncation and len(result) > 5000:
            result = result[:5000] + f"\n... ({len(data_items)} total items, truncated)"
            
        return result
    
    def build_context_with_truncation(self, days_date: str, enable_truncation: bool) -> str:
        """Build daily context with optional truncation"""
        context_parts = [f"Date: {days_date}"]
        
        # Get news headlines
        news_items = self.llm_repo.get_news_for_context(days_date)
        if news_items:
            context_parts.append("News Headlines:")
            for item in news_items:
                context_parts.append(f"- {item['title']}")
                if item.get('snippet'):
                    context_parts.append(f"  {item['snippet']}")
        
        # Get weather data
        weather_data = self.llm_repo.get_weather_for_context(days_date)
        if weather_data and 'data' in weather_data and weather_data['data']:
            weather_info = weather_data['data'][0]
            context_parts.append(f"Weather: {weather_info.get('weather', 'N/A')}")
            if 'temperature' in weather_info:
                context_parts.append(f"Temperature: {weather_info['temperature']}°C")
        
        # Get limitless/activity data with truncation control
        activity_items = self.llm_repo.get_activities_for_context(days_date)
        if activity_items:
            context_parts.append("Activities:")
            for item in activity_items:
                if item['content']:
                    content = item['content']
                    # Apply truncation only if enabled
                    if enable_truncation:
                        content = content[:200]
                        if len(item['content']) > 200:
                            content += "..."
                    context_parts.append(f"- {content}")
        
        return "\n".join(context_parts)
    
    async def test_llm_performance(self, prompt: str, context: str) -> Dict[str, Any]:
        """Test LLM performance with given prompt and context"""
        full_prompt = prompt.replace("{{LIMITLESS_DAY}}", context)
        
        start_time = time.time()
        
        try:
            # Use the LLM service to generate response (this ensures proper provider usage)
            print(f"    Calling LLM with prompt length: {len(full_prompt)} characters")
            
            # Call the LLM provider through the service
            if hasattr(self.llm_service.llm_provider, 'generate_response'):
                llm_response = await self.llm_service.llm_provider.generate_response(
                    prompt=full_prompt
                )
                response = llm_response.content if hasattr(llm_response, 'content') else str(llm_response)
            else:
                # Alternative method if the provider interface is different
                response = await self.llm_service.llm_provider.generate(
                    prompt=full_prompt
                )
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"    LLM response received in {duration:.2f}s, response length: {len(response) if response else 0}")
            
            return {
                'success': True,
                'duration': duration,
                'prompt_length': len(full_prompt),
                'response_length': len(response) if response else 0,
                'response': response
            }
            
        except Exception as e:
            end_time = time.time()
            print(f"    LLM call failed after {end_time - start_time:.2f}s: {e}")
            return {
                'success': False,
                'duration': end_time - start_time,
                'prompt_length': len(full_prompt),
                'error': str(e)
            }
    
    async def run_date_test(self, days_date: str) -> Dict[str, Any]:
        """Run complete test for a single date"""
        print(f"Testing date: {days_date}")
        
        # Get raw data
        limitless_data = self.get_limitless_data_for_date(days_date)
        
        # Get the default prompt
        prompt_content = await self.llm_service._get_selected_prompt(days_date)
        if not prompt_content:
            # Fallback to basic prompt
            prompt_content = "Summarize the following day:\n\n{{LIMITLESS_DAY}}"
        
        # Test truncated version
        print("  Testing truncated...")
        truncated_context = self.build_context_with_truncation(days_date, enable_truncation=True)
        truncated_formatted = self.format_data_with_truncation(limitless_data, enable_truncation=True)
        truncated_full_context = truncated_context + "\n\nDetailed Activities:\n" + truncated_formatted
        
        truncated_result = await self.test_llm_performance(prompt_content, truncated_full_context)
        
        # Test untruncated version
        print("  Testing untruncated...")
        untruncated_context = self.build_context_with_truncation(days_date, enable_truncation=False)
        untruncated_formatted = self.format_data_with_truncation(limitless_data, enable_truncation=False)
        untruncated_full_context = untruncated_context + "\n\nDetailed Activities:\n" + untruncated_formatted
        
        untruncated_result = await self.test_llm_performance(prompt_content, untruncated_full_context)
        
        # Calculate metrics
        data_stats = {
            'limitless_items': len(limitless_data),
            'total_raw_chars': sum(len(item.get('content', '')) for item in limitless_data),
            'truncated_context_chars': len(truncated_full_context),
            'untruncated_context_chars': len(untruncated_full_context),
            'context_size_ratio': len(untruncated_full_context) / len(truncated_full_context) if len(truncated_full_context) > 0 else 0,
            'chars_saved_by_truncation': len(untruncated_full_context) - len(truncated_full_context)
        }
        
        return {
            'days_date': days_date,
            'data_stats': data_stats,
            'truncated': truncated_result,
            'untruncated': untruncated_result,
            'performance_impact': {
                'duration_ratio': untruncated_result['duration'] / truncated_result['duration'] if truncated_result['duration'] > 0 else None,
                'duration_difference': untruncated_result['duration'] - truncated_result['duration'],
                'prompt_size_ratio': untruncated_result['prompt_length'] / truncated_result['prompt_length'] if truncated_result['prompt_length'] > 0 else None
            }
        }
    
    async def run_performance_test(self, num_dates: int = 20) -> List[Dict[str, Any]]:
        """Run the complete performance test"""
        print("Starting simplified truncation performance test...")
        
        # Get sample dates
        test_dates = self.get_dates_with_limitless_data(num_dates)
        print(f"Testing {len(test_dates)} dates")
        
        results = []
        
        for i, days_date in enumerate(test_dates):
            print(f"\nTest {i+1}/{len(test_dates)}")
            
            try:
                result = await self.run_date_test(days_date)
                results.append(result)
                
                # Print quick summary
                perf = result['performance_impact']
                data = result['data_stats']
                print(f"  Duration: {result['truncated']['duration']:.2f}s → {result['untruncated']['duration']:.2f}s ({perf['duration_ratio']:.2f}x)")
                print(f"  Context: {data['truncated_context_chars']} → {data['untruncated_context_chars']} chars ({data['context_size_ratio']:.2f}x)")
                
            except Exception as e:
                print(f"  Error: {e}")
                results.append({
                    'days_date': days_date,
                    'error': str(e)
                })
        
        return results
    
    def analyze_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze test results"""
        successful_tests = [r for r in results if 'error' not in r and 
                           r.get('truncated', {}).get('success', False) and 
                           r.get('untruncated', {}).get('success', False)]
        
        print(f"Debug: Found {len(successful_tests)} successful tests out of {len(results)} total")
        for i, r in enumerate(results):
            if 'error' in r:
                print(f"  Test {i}: Error - {r['error']}")
            else:
                t_success = r.get('truncated', {}).get('success', False)
                u_success = r.get('untruncated', {}).get('success', False)
                print(f"  Test {i}: Truncated success: {t_success}, Untruncated success: {u_success}")
                if not t_success:
                    print(f"    Truncated error: {r.get('truncated', {}).get('error', 'unknown')}")
                if not u_success:
                    print(f"    Untruncated error: {r.get('untruncated', {}).get('error', 'unknown')}")
        
        if not successful_tests:
            return {'error': 'No successful tests to analyze'}
        
        # Extract metrics
        duration_ratios = [r['performance_impact']['duration_ratio'] for r in successful_tests if r['performance_impact']['duration_ratio']]
        duration_differences = [r['performance_impact']['duration_difference'] for r in successful_tests]
        context_size_ratios = [r['data_stats']['context_size_ratio'] for r in successful_tests]
        chars_saved = [r['data_stats']['chars_saved_by_truncation'] for r in successful_tests]
        
        truncated_durations = [r['truncated']['duration'] for r in successful_tests]
        untruncated_durations = [r['untruncated']['duration'] for r in successful_tests]
        
        analysis = {
            'summary': {
                'total_tests': len(results),
                'successful_tests': len(successful_tests),
                'failed_tests': len(results) - len(successful_tests)
            },
            'performance_impact': {
                'duration_ratio': {
                    'mean': statistics.mean(duration_ratios),
                    'median': statistics.median(duration_ratios),
                    'min': min(duration_ratios),
                    'max': max(duration_ratios),
                    'stdev': statistics.stdev(duration_ratios) if len(duration_ratios) > 1 else 0
                },
                'duration_difference_seconds': {
                    'mean': statistics.mean(duration_differences),
                    'median': statistics.median(duration_differences),
                    'min': min(duration_differences),
                    'max': max(duration_differences)
                }
            },
            'context_impact': {
                'size_ratio': {
                    'mean': statistics.mean(context_size_ratios),
                    'median': statistics.median(context_size_ratios),
                    'min': min(context_size_ratios),
                    'max': max(context_size_ratios)
                },
                'chars_saved_by_truncation': {
                    'mean': statistics.mean(chars_saved),
                    'median': statistics.median(chars_saved),
                    'min': min(chars_saved),
                    'max': max(chars_saved)
                }
            },
            'baseline_performance': {
                'truncated_duration': {
                    'mean': statistics.mean(truncated_durations),
                    'median': statistics.median(truncated_durations)
                },
                'untruncated_duration': {
                    'mean': statistics.mean(untruncated_durations),
                    'median': statistics.median(untruncated_durations)
                }
            }
        }
        
        return analysis


@pytest.mark.asyncio
async def test_simple_truncation_performance():
    """Run the simplified truncation performance test"""
    test = SimpleTruncationTest()
    await test.setup()
    
    # Run test with more dates for comprehensive analysis
    results = await test.run_performance_test(num_dates=10)
    analysis = test.analyze_results(results)
    
    # Print results
    print("\n" + "="*80)
    print("SIMPLIFIED TRUNCATION PERFORMANCE TEST RESULTS")
    print("="*80)
    
    if 'error' in analysis:
        print(f"Error: {analysis['error']}")
        return
    
    print(f"\nTest Summary:")
    print(f"  Total tests: {analysis['summary']['total_tests']}")
    print(f"  Successful tests: {analysis['summary']['successful_tests']}")
    print(f"  Failed tests: {analysis['summary']['failed_tests']}")
    
    print(f"\nPerformance Impact:")
    perf = analysis['performance_impact']
    print(f"  Duration ratio (untruncated/truncated): {perf['duration_ratio']['mean']:.2f}x (median: {perf['duration_ratio']['median']:.2f}x)")
    print(f"  Duration difference: +{perf['duration_difference_seconds']['mean']:.2f}s (median: +{perf['duration_difference_seconds']['median']:.2f}s)")
    print(f"  Range: {perf['duration_ratio']['min']:.2f}x to {perf['duration_ratio']['max']:.2f}x")
    
    print(f"\nContext Size Impact:")
    ctx = analysis['context_impact']
    print(f"  Size ratio (untruncated/truncated): {ctx['size_ratio']['mean']:.2f}x (median: {ctx['size_ratio']['median']:.2f}x)")
    print(f"  Characters saved by truncation: {ctx['chars_saved_by_truncation']['mean']:.0f} (median: {ctx['chars_saved_by_truncation']['median']:.0f})")
    print(f"  Range: {ctx['size_ratio']['min']:.2f}x to {ctx['size_ratio']['max']:.2f}x")
    
    print(f"\nBaseline Performance:")
    base = analysis['baseline_performance']
    print(f"  Truncated duration: {base['truncated_duration']['mean']:.2f}s (median: {base['truncated_duration']['median']:.2f}s)")
    print(f"  Untruncated duration: {base['untruncated_duration']['mean']:.2f}s (median: {base['untruncated_duration']['median']:.2f}s)")
    
    # Basic assertions
    assert analysis['summary']['successful_tests'] > 0, "No successful tests completed"
    assert perf['duration_ratio']['mean'] > 0, "Invalid performance ratio"
    
    return results, analysis


if __name__ == "__main__":
    # Run the test directly
    asyncio.run(test_simple_truncation_performance())