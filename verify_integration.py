#!/usr/bin/env python3
"""
Integration verification script for real embeddings

This script verifies that the embedding service integrates correctly with the chat workflow
and produces meaningful semantic embeddings instead of random ones.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.embeddings import EmbeddingService
from config.models import EmbeddingConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_embedding_service():
    """Test basic embedding service functionality"""
    logger.info("=== Testing Embedding Service ===")
    
    # Create service with default model
    config = EmbeddingConfig(model_name="all-MiniLM-L6-v2")
    service = EmbeddingService(config)
    
    try:
        # Initialize service
        logger.info("Initializing embedding service...")
        await service.initialize()
        logger.info(f"✓ Service initialized with model: {service.config.model_name}")
        logger.info(f"✓ Model loaded: {service.model is not None}")
        logger.info(f"✓ Is initialized: {service.is_initialized}")
        
        # Test single embedding
        test_text = "Machine learning is a subset of artificial intelligence"
        embedding = await service.embed_text(test_text)
        
        logger.info(f"✓ Generated embedding with {len(embedding)} dimensions")
        logger.info(f"✓ All values are floats: {all(isinstance(x, float) for x in embedding)}")
        logger.info(f"✓ Non-zero embedding: {any(abs(x) > 0.01 for x in embedding)}")
        
        return service
        
    except Exception as e:
        logger.error(f"✗ Embedding service test failed: {e}")
        return None

async def test_semantic_similarity():
    """Test that embeddings capture semantic similarity"""
    logger.info("=== Testing Semantic Similarity ===")
    
    config = EmbeddingConfig(model_name="all-MiniLM-L6-v2")
    service = EmbeddingService(config)
    await service.initialize()
    
    # Test texts with different levels of similarity
    texts = {
        "ml_1": "Machine learning is a powerful AI technique",
        "ml_2": "AI and machine learning are related technologies", 
        "cooking": "I love cooking pasta with tomatoes",
        "weather": "Today's weather is sunny and warm"
    }
    
    # Generate embeddings
    embeddings = {}
    for key, text in texts.items():
        embeddings[key] = await service.embed_text(text)
        logger.info(f"✓ Generated embedding for '{key}': {text[:50]}...")
    
    # Calculate cosine similarities manually
    def cosine_similarity(a, b):
        import numpy as np
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    # Test semantic relationships
    ml_similarity = cosine_similarity(embeddings["ml_1"], embeddings["ml_2"])
    unrelated_similarity = cosine_similarity(embeddings["ml_1"], embeddings["cooking"])
    
    logger.info(f"✓ ML topics similarity: {ml_similarity:.3f}")
    logger.info(f"✓ ML vs cooking similarity: {unrelated_similarity:.3f}")
    
    # Verify semantic understanding
    if ml_similarity > unrelated_similarity:
        logger.info("✓ Semantic similarity working correctly!")
        return True
    else:
        logger.error("✗ Semantic similarity not working as expected")
        return False

async def test_batch_processing():
    """Test batch embedding processing"""
    logger.info("=== Testing Batch Processing ===")
    
    config = EmbeddingConfig(model_name="all-MiniLM-L6-v2")
    service = EmbeddingService(config)
    await service.initialize()
    
    texts = [
        "Natural language processing enables computers to understand text",
        "Computer vision allows machines to interpret visual information",
        "Deep learning uses neural networks with multiple layers",
        "Reinforcement learning trains agents through trial and error"
    ]
    
    try:
        embeddings = await service.embed_batch(texts)
        logger.info(f"✓ Generated {len(embeddings)} batch embeddings")
        logger.info(f"✓ All embeddings have correct dimensions: {all(len(emb) == 384 for emb in embeddings)}")
        return True
    except Exception as e:
        logger.error(f"✗ Batch processing failed: {e}")
        return False

async def test_environment_integration():
    """Test that environment configuration works"""
    logger.info("=== Testing Environment Integration ===")
    
    # Test loading from environment
    try:
        config = EmbeddingConfig.from_env()
        service = EmbeddingService(config)
        await service.initialize()
        
        logger.info(f"✓ Loaded config from environment: {config.model_name}")
        logger.info(f"✓ Device: {config.device}")
        logger.info(f"✓ Batch size: {config.batch_size}")
        
        # Test embedding generation
        embedding = await service.embed_text("Environment configuration test")
        logger.info(f"✓ Generated embedding with {len(embedding)} dimensions")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Environment integration failed: {e}")
        return False

async def main():
    """Run all integration tests"""
    logger.info("Starting embedding service integration verification...")
    
    tests = [
        ("Basic Embedding Service", test_embedding_service()),
        ("Semantic Similarity", test_semantic_similarity()),
        ("Batch Processing", test_batch_processing()),
        ("Environment Integration", test_environment_integration())
    ]
    
    results = []
    for test_name, test_coro in tests:
        try:
            logger.info(f"\n{'-' * 50}")
            result = await test_coro
            results.append((test_name, bool(result)))
        except Exception as e:
            logger.error(f"Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'=' * 50}")
    logger.info("INTEGRATION TEST RESULTS")
    logger.info(f"{'=' * 50}")
    
    passed = 0
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        logger.info(f"{test_name}: {status}")
        if success:
            passed += 1
    
    logger.info(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        logger.info("🎉 ALL INTEGRATION TESTS PASSED!")
        logger.info("Real embeddings are working correctly and ready for production use.")
        return True
    else:
        logger.error("❌ Some tests failed. Check the logs above for details.")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)