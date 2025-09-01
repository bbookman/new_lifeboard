#!/usr/bin/env python3
"""
Performance benchmarking script for async service layer operations
Phase 2 of async refactor validation
"""

import asyncio
import time
import logging
from typing import Dict

from config.factory import ConfigFactory
from core.database import DatabaseService

# Setup logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise
logger = logging.getLogger(__name__)


async def benchmark_async_database_operations() -> Dict[str, float]:
    """Benchmark async database operations directly"""
    
    # Load configuration
    config = ConfigFactory.create_config()
    
    # Initialize database service
    database = DatabaseService(config.database.path)
    
    results = {}
    
    try:
        # Benchmark 1: Settings operations
        print("Benchmarking settings operations...")
        start_time = time.time()
        
        await database.async_set_setting("benchmark_key", "benchmark_value")
        setting_value = await database.async_get_setting("benchmark_key", "default")
        
        results["settings_operations"] = time.time() - start_time
        
        # Benchmark 2: Database stats
        print("Benchmarking database stats...")
        start_time = time.time()
        
        stats = await database.async_get_database_stats()
        
        results["database_stats"] = time.time() - start_time
        
        # Benchmark 3: Chat operations  
        print("Benchmarking chat operations...")
        start_time = time.time()
        
        await database.async_store_chat_message("Benchmark user message", "Benchmark assistant response")
        chat_history = await database.async_get_chat_history(limit=5)
        
        results["chat_operations"] = time.time() - start_time
        
        # Benchmark 4: Batch operations
        print("Benchmarking concurrent operations...")
        start_time = time.time()
        
        # Test multiple concurrent database calls
        tasks = []
        for i in range(5):
            tasks.append(database.async_get_setting(f"test_key_{i}", "default"))
        
        await asyncio.gather(*tasks)
        
        results["concurrent_operations"] = time.time() - start_time
        
        print("Benchmark completed successfully!")
        return results
        
    except Exception as e:
        logger.error(f"Benchmark error: {e}")
        raise


async def main():
    """Run performance benchmarks and display results"""
    print("🚀 Starting async service layer performance benchmarks...")
    print("=" * 60)
    
    try:
        benchmark_results = await benchmark_async_database_operations()
        
        print("\n📊 BENCHMARK RESULTS")
        print("=" * 60)
        
        total_time = 0
        for operation, duration in benchmark_results.items():
            print(f"{operation:<30} {duration:.4f}s")
            total_time += duration
        
        print("-" * 60)
        print(f"{'TOTAL TIME':<30} {total_time:.4f}s")
        
        # Performance assessment
        print("\n📈 PERFORMANCE ASSESSMENT")
        print("=" * 60)
        
        if total_time < 0.1:
            print("✅ EXCELLENT: Async operations performing very well (<100ms total)")
        elif total_time < 0.5:
            print("✅ GOOD: Async operations performing adequately (<500ms total)")
        elif total_time < 1.0:
            print("⚠️ ACCEPTABLE: Some optimization opportunities available (<1s total)")
        else:
            print("❌ NEEDS IMPROVEMENT: Significant performance issues detected (>1s total)")
        
        # Analysis
        print("\n💡 ANALYSIS")
        print("=" * 60)
        
        if benchmark_results.get("concurrent_operations", 0) < benchmark_results.get("settings_operations", 0) * 5:
            print("✅ Concurrent operations show good async performance gains")
        else:
            print("⚠️ Concurrent operations may not be fully optimized")
        
        print("\n✅ Phase 2 async refactor performance validation completed!")
        
        return benchmark_results
        
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        logger.exception("Benchmark error details:")
        return {}


if __name__ == "__main__":
    asyncio.run(main())