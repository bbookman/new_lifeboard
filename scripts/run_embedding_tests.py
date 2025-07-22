#!/usr/bin/env python3
"""Script to run embedding tests and benchmarks."""

import sys
import os
import subprocess

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_tests():
    """Run the embedding tests."""
    print("🧪 Running Enhanced Embedding Tests...")
    
    try:
        # Run the enhanced embedding tests
        result = subprocess.run([
            sys.executable, "-m", "pytest", 
            "tests/test_enhanced_embeddings.py", 
            "-v", "--tb=short"
        ], capture_output=True, text=True)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ All tests passed!")
            return True
        else:
            print("❌ Some tests failed!")
            return False
            
    except Exception as e:
        print(f"❌ Error running tests: {e}")
        return False

def run_benchmark_demo():
    """Run a small benchmark demo."""
    print("\n🚀 Running Embedding Benchmark Demo...")
    
    try:
        from evaluation.embedding_benchmarks import EmbeddingBenchmarkFramework, BenchmarkConfig
        
        # Small demo configuration
        config = BenchmarkConfig(
            test_sample_size=10,  # Very small for demo
            similarity_threshold=0.5
        )
        
        framework = EmbeddingBenchmarkFramework(config)
        
        # Test with just the current model
        test_models = ['all-MiniLM-L6-v2']  # Just one model for demo
        
        print(f"Testing models: {test_models}")
        results = framework.run_full_benchmark(test_models)
        
        if results:
            print("\n📊 Demo Results:")
            for model, metrics in results.items():
                print(f"  {model}:")
                print(f"    Overall Score: {metrics.overall_score:.3f}")
                print(f"    Embedding Time: {metrics.embedding_time:.2f}s")
                print(f"    Dimension: {metrics.dimension}")
        else:
            print("❌ No benchmark results generated")
            
    except Exception as e:
        print(f"❌ Error running benchmark demo: {e}")

if __name__ == "__main__":
    success = run_tests()
    
    if success:
        run_benchmark_demo()
    
    sys.exit(0 if success else 1)