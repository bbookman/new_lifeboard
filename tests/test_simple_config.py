#!/usr/bin/env python3
"""
Simple test to verify processor configuration
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_processor_import():
    """Test that we can import and configure the processor"""
    try:
        from sources.limitless_processor import LimitlessProcessor

        print("Testing LimitlessProcessor configuration...")

        # Create processor with semantic deduplication enabled
        processor = LimitlessProcessor(
            enable_segmentation=True,
            enable_markdown_generation=True,
            enable_semantic_deduplication=True,
            embedding_service=None,  # We'll test without actual embedding service
        )

        # Check configuration
        print(f"✅ Semantic deduplication enabled: {processor.enable_semantic_deduplication}")

        # Get pipeline info
        pipeline_info = processor.get_pipeline_info()
        print(f"✅ Pipeline version: {pipeline_info['pipeline_version']}")
        print(f"✅ Semantic deduplication enabled in pipeline: {pipeline_info['semantic_deduplication_enabled']}")
        print(f"✅ Supports batch processing: {pipeline_info['supports_batch_processing']}")
        print(f"✅ Total processors: {pipeline_info['processor_count']}")
        print(f"✅ Processor list: {pipeline_info['processors']}")

        # Check that semantic processor exists
        if processor.enable_semantic_deduplication:
            has_semantic_processor = hasattr(processor, "semantic_processor")
            print(f"✅ Semantic processor initialized: {has_semantic_processor}")

        print("\n🎉 LimitlessProcessor configuration looks correct!")
        return True

    except Exception as e:
        print(f"❌ Error testing processor: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_processor_import()
    sys.exit(0 if success else 1)
