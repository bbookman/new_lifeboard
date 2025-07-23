#!/usr/bin/env python3
"""
Test suite for embedding quality analysis

Tests embedding quality analysis functionality including:
- Quality metrics calculation
- Vector distribution analysis
- Content quality assessment
- Model performance testing
- Edge cases and error handling
"""

import unittest
import asyncio
import tempfile
import os
import numpy as np
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.analyze_embedding_quality import (
    EmbeddingQualityAnalyzer, EmbeddingQualityMetrics, ContentAnalysis
)
from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService


class TestEmbeddingQualityAnalyzer(unittest.TestCase):
    """Test cases for EmbeddingQualityAnalyzer"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.analyzer = EmbeddingQualityAnalyzer()
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_count_outliers(self):
        """Test outlier detection using z-score method"""
        # Normal distribution - should have few outliers
        normal_norms = [1.0] * 100 + [1.1, 0.9] * 10  # 120 values, mostly around 1.0
        outliers = self.analyzer._count_outliers(normal_norms, threshold=2.0)
        self.assertEqual(outliers, 0, "Normal distribution should have no outliers with z > 2")
        
        # Distribution with clear outliers
        outlier_norms = [1.0] * 50 + [5.0, 0.1]  # 52 values with 2 clear outliers
        outliers = self.analyzer._count_outliers(outlier_norms, threshold=2.0)
        self.assertEqual(outliers, 2, "Should detect 2 clear outliers")
        
        # Empty list edge case
        empty_outliers = self.analyzer._count_outliers([], threshold=2.0)
        self.assertEqual(empty_outliers, 0, "Empty list should have 0 outliers")
        
        # Single value edge case
        single_outliers = self.analyzer._count_outliers([1.0], threshold=2.0)
        self.assertEqual(single_outliers, 0, "Single value should have 0 outliers")
        
        # Constant values edge case
        constant_outliers = self.analyzer._count_outliers([1.0] * 10, threshold=2.0)
        self.assertEqual(constant_outliers, 0, "Constant values should have 0 outliers")
    
    def test_count_duplicates(self):
        """Test duplicate vector detection"""
        # Create test embeddings with known duplicates
        embedding_a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        embedding_b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        embedding_c = np.array([1.0, 0.0, 0.0], dtype=np.float32)  # Duplicate of A
        
        embeddings = [embedding_a, embedding_b, embedding_c]
        duplicates = self.analyzer._count_duplicates(embeddings)
        self.assertEqual(duplicates, 1, "Should detect 1 duplicate")
        
        # All unique embeddings
        unique_embeddings = [
            np.array([1.0, 0.0], dtype=np.float32),
            np.array([0.0, 1.0], dtype=np.float32),
            np.array([0.5, 0.5], dtype=np.float32)
        ]
        duplicates = self.analyzer._count_duplicates(unique_embeddings)
        self.assertEqual(duplicates, 0, "Unique embeddings should have 0 duplicates")
        
        # Empty list edge case
        duplicates = self.analyzer._count_duplicates([])
        self.assertEqual(duplicates, 0, "Empty list should have 0 duplicates")
        
        # Single embedding edge case
        duplicates = self.analyzer._count_duplicates([embedding_a])
        self.assertEqual(duplicates, 0, "Single embedding should have 0 duplicates")
    
    def test_calculate_similarity_matrix(self):
        """Test similarity matrix calculation"""
        # Create test embeddings
        embeddings = [
            np.array([1.0, 0.0], dtype=np.float32),  # Unit vector
            np.array([0.0, 1.0], dtype=np.float32),  # Orthogonal unit vector
            np.array([1.0, 0.0], dtype=np.float32),  # Identical to first
        ]
        
        similarity_matrix = self.analyzer._calculate_similarity_matrix(embeddings)
        
        # Check dimensions
        self.assertEqual(similarity_matrix.shape, (3, 3), "Similarity matrix should be 3x3")
        
        # Check diagonal (self-similarity should be 1.0)
        np.testing.assert_array_almost_equal(
            np.diag(similarity_matrix), [1.0, 1.0, 1.0], 
            decimal=6, err_msg="Diagonal should be all 1.0"
        )
        
        # Check orthogonal vectors (similarity should be ~0)
        self.assertAlmostEqual(
            similarity_matrix[0, 1], 0.0, places=6,
            msg="Orthogonal vectors should have similarity ~0"
        )
        
        # Check identical vectors (similarity should be 1.0)
        self.assertAlmostEqual(
            similarity_matrix[0, 2], 1.0, places=6,
            msg="Identical vectors should have similarity 1.0"
        )
        
        # Check symmetry
        np.testing.assert_array_almost_equal(
            similarity_matrix, similarity_matrix.T,
            decimal=6, err_msg="Similarity matrix should be symmetric"
        )
        
        # Edge case: single embedding
        single_matrix = self.analyzer._calculate_similarity_matrix([embeddings[0]])
        np.testing.assert_array_equal(single_matrix, [[1.0]], "Single embedding matrix should be [[1.0]]")
        
        # Edge case: empty list
        empty_matrix = self.analyzer._calculate_similarity_matrix([])
        self.assertEqual(empty_matrix.shape, (0, 0), "Empty matrix should have shape (0, 0)")
    
    def test_calculate_quality_scores(self):
        """Test quality score calculation"""
        # Create test data
        embeddings = [
            np.array([1.0, 0.0], dtype=np.float32),
            np.array([0.0, 1.0], dtype=np.float32),
            np.array([0.5, 0.5], dtype=np.float32)
        ]
        norms = [np.linalg.norm(emb) for emb in embeddings]
        
        content_analysis = ContentAnalysis(
            content_length_stats={'mean': 500, 'empty_count': 0},
            content_type_classification={},
            semantic_density_scores=[0.8, 0.7, 0.9],
            preprocessing_quality={'preprocessing_coverage': 0.8}
        )
        
        quality_scores = self.analyzer._calculate_quality_scores(embeddings, norms, content_analysis)
        
        # Check that all scores are present and in valid range [0, 1]
        expected_keys = ['vector_quality', 'content_quality', 'preprocessing_quality', 'overall_quality']
        for key in expected_keys:
            self.assertIn(key, quality_scores, f"Quality scores should contain {key}")
            self.assertGreaterEqual(quality_scores[key], 0.0, f"{key} should be >= 0")
            self.assertLessEqual(quality_scores[key], 1.0, f"{key} should be <= 1")
        
        # Edge case: empty embeddings
        empty_scores = self.analyzer._calculate_quality_scores([], [], content_analysis)
        self.assertEqual(empty_scores, {}, "Empty embeddings should return empty scores")
    
    def test_create_empty_metrics(self):
        """Test creation of empty metrics"""
        empty_metrics = self.analyzer._create_empty_metrics()
        
        self.assertIsInstance(empty_metrics, EmbeddingQualityMetrics)
        self.assertEqual(empty_metrics.total_embeddings, 0)
        self.assertEqual(empty_metrics.dimension, 0)
        self.assertEqual(empty_metrics.mean_norm, 0.0)
        self.assertEqual(empty_metrics.std_norm, 0.0)
        self.assertEqual(empty_metrics.norm_distribution, [])
        self.assertIsNone(empty_metrics.similarity_matrix)
        self.assertEqual(empty_metrics.outlier_count, 0)
        self.assertEqual(empty_metrics.zero_vector_count, 0)
        self.assertEqual(empty_metrics.duplicate_count, 0)
        self.assertEqual(empty_metrics.content_type_distribution, {})
        self.assertEqual(empty_metrics.namespace_distribution, {})
        self.assertEqual(empty_metrics.quality_scores, {})
    
    def test_generate_recommendations(self):
        """Test recommendation generation based on metrics"""
        # High quality metrics
        good_metrics = EmbeddingQualityMetrics(
            total_embeddings=1000,
            dimension=384,
            mean_norm=1.0,
            std_norm=0.1,
            norm_distribution=[1.0] * 1000,
            similarity_matrix=None,
            outlier_count=10,      # 1% outliers
            zero_vector_count=5,   # 0.5% zero vectors
            duplicate_count=15,    # 1.5% duplicates
            content_type_distribution={},
            namespace_distribution={},
            quality_scores={
                'overall_quality': 0.85,
                'vector_quality': 0.90,
                'content_quality': 0.80,
                'preprocessing_quality': 0.85
            }
        )
        
        good_recommendations = self.analyzer._generate_recommendations(good_metrics)
        self.assertTrue(any("Good" in rec or "✅" in rec for rec in good_recommendations))
        
        # Poor quality metrics
        poor_metrics = EmbeddingQualityMetrics(
            total_embeddings=100,
            dimension=384,
            mean_norm=0.5,
            std_norm=0.5,
            norm_distribution=[0.5] * 100,
            similarity_matrix=None,
            outlier_count=20,      # 20% outliers
            zero_vector_count=10,  # 10% zero vectors
            duplicate_count=30,    # 30% duplicates
            content_type_distribution={},
            namespace_distribution={},
            quality_scores={
                'overall_quality': 0.3,
                'vector_quality': 0.4,
                'content_quality': 0.3,
                'preprocessing_quality': 0.2
            }
        )
        
        poor_recommendations = self.analyzer._generate_recommendations(poor_metrics)
        self.assertTrue(any("FIX" in rec or "IMPROVE" in rec for rec in poor_recommendations))
        self.assertTrue(len(poor_recommendations) > len(good_recommendations))
        
        # Zero embeddings case
        zero_metrics = EmbeddingQualityMetrics(
            total_embeddings=0,
            dimension=0,
            mean_norm=0.0,
            std_norm=0.0,
            norm_distribution=[],
            similarity_matrix=None,
            outlier_count=0,
            zero_vector_count=0,
            duplicate_count=0,
            content_type_distribution={},
            namespace_distribution={},
            quality_scores={}
        )
        
        zero_recommendations = self.analyzer._generate_recommendations(zero_metrics)
        self.assertTrue(any("URGENT" in rec for rec in zero_recommendations))
    
    def test_generate_quality_report(self):
        """Test quality report generation"""
        # Create sample metrics
        metrics = EmbeddingQualityMetrics(
            total_embeddings=500,
            dimension=384,
            mean_norm=1.0,
            std_norm=0.05,
            norm_distribution=[1.0] * 500,
            similarity_matrix=np.eye(3),  # Simple identity matrix
            outlier_count=5,
            zero_vector_count=2,
            duplicate_count=8,
            content_type_distribution={'conversation': 200, 'qa': 150, 'general': 150},
            namespace_distribution={'limitless': 300, 'manual': 200},
            quality_scores={
                'overall_quality': 0.75,
                'vector_quality': 0.80,
                'content_quality': 0.70,
                'preprocessing_quality': 0.75
            }
        )
        
        performance_results = {
            'test query': {
                'embedding_dimension': 384,
                'embedding_norm': 1.0,
                'embedding_time_seconds': 0.05,
                'search_results_count': 5,
                'top_similarity': 0.85
            },
            'error query': {
                'error': 'Test error message'
            }
        }
        
        report = self.analyzer.generate_quality_report(metrics, performance_results)
        
        # Check that report contains expected sections
        self.assertIn("EMBEDDING QUALITY ANALYSIS REPORT", report)
        self.assertIn("VECTOR STORE STATISTICS", report)
        self.assertIn("QUALITY ISSUES DETECTED", report)
        self.assertIn("QUALITY SCORES", report)
        self.assertIn("NAMESPACE DISTRIBUTION", report)
        self.assertIn("CONTENT TYPE DISTRIBUTION", report)
        self.assertIn("MODEL PERFORMANCE TESTS", report)
        self.assertIn("RECOMMENDATIONS", report)
        
        # Check that key metrics are included
        self.assertIn("Total Embeddings: 500", report)
        self.assertIn("Dimension: 384", report)
        self.assertIn("limitless: 300", report)
        self.assertIn("manual: 200", report)
        
        # Check performance test results
        self.assertIn("test query", report)
        self.assertIn("Embedding Time: 0.050s", report)
        self.assertIn("error query", report)
        self.assertIn("ERROR: Test error message", report)


class TestEmbeddingQualityIntegration(unittest.TestCase):
    """Integration tests for embedding quality analysis"""
    
    def setUp(self):
        """Set up integration test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        
    def tearDown(self):
        """Clean up integration test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('scripts.analyze_embedding_quality.EmbeddingService')
    @patch('scripts.analyze_embedding_quality.VectorStoreService')
    @patch('scripts.analyze_embedding_quality.DatabaseService')
    async def test_analyze_embedding_quality_with_mocks(self, mock_db, mock_vs, mock_es):
        """Test embedding quality analysis with mocked services"""
        # Set up mocks
        mock_database = Mock()
        mock_vector_store = Mock()
        mock_embedding_service = AsyncMock()
        
        mock_db.return_value = mock_database
        mock_vs.return_value = mock_vector_store
        mock_es.return_value = mock_embedding_service
        
        # Configure mock returns
        mock_database.get_database_stats.return_value = {
            'total_items': 100,
            'namespace_counts': {'test': 100},
            'embedding_status': {'completed': 100},
            'active_sources': 1
        }
        
        mock_vector_store.get_stats.return_value = {
            'total_vectors': 100,
            'dimension': 384
        }
        
        # Create test vectors
        test_vectors = {
            f"test:{i}": np.random.rand(384).astype(np.float32)
            for i in range(10)
        }
        mock_vector_store.vectors = test_vectors
        
        # Configure embedding service
        mock_embedding_service.initialize = AsyncMock()
        mock_embedding_service.embed_text = AsyncMock(return_value=np.random.rand(384))
        
        # Configure database connection mock
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = [
            {
                'id': 'test:1',
                'namespace': 'test',
                'content': 'Test content 1',
                'metadata': None,
                'content_quality_score': 0.8,
                'semantic_density': 0.7
            },
            {
                'id': 'test:2', 
                'namespace': 'test',
                'content': 'Test content 2',
                'metadata': None,
                'content_quality_score': 0.9,
                'semantic_density': 0.8
            }
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_database.get_connection.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_database.get_connection.return_value.__exit__ = Mock(return_value=None)
        
        # Create analyzer and run analysis
        analyzer = EmbeddingQualityAnalyzer()
        analyzer.database = mock_database
        analyzer.vector_store = mock_vector_store
        analyzer.embedding_service = mock_embedding_service
        
        metrics = await analyzer.analyze_embedding_quality()
        
        # Verify results
        self.assertIsInstance(metrics, EmbeddingQualityMetrics)
        self.assertEqual(metrics.total_embeddings, 10)
        self.assertEqual(metrics.dimension, 384)
        self.assertGreater(metrics.mean_norm, 0)
        self.assertIsNotNone(metrics.similarity_matrix)
        self.assertIsInstance(metrics.quality_scores, dict)
    
    @patch('scripts.analyze_embedding_quality.EmbeddingService')
    async def test_model_performance_testing(self, mock_es):
        """Test model performance testing functionality"""
        # Set up mock embedding service
        mock_embedding_service = AsyncMock()
        mock_es.return_value = mock_embedding_service
        
        # Configure mock to return consistent embeddings
        test_embedding = np.random.rand(384).astype(np.float32)
        mock_embedding_service.embed_text = AsyncMock(return_value=test_embedding)
        
        # Create mock vector store with search results
        mock_vector_store = Mock()
        mock_vector_store.search.return_value = [
            ('test:1', 0.95),
            ('test:2', 0.87),
            ('test:3', 0.73)
        ]
        
        # Create analyzer and test
        analyzer = EmbeddingQualityAnalyzer()
        analyzer.embedding_service = mock_embedding_service
        analyzer.vector_store = mock_vector_store
        
        results = await analyzer.test_model_performance()
        
        # Verify results structure
        self.assertIsInstance(results, dict)
        self.assertGreater(len(results), 0)
        
        # Check that each test query has expected metrics
        for query, result in results.items():
            if 'error' not in result:
                self.assertIn('embedding_dimension', result)
                self.assertIn('embedding_norm', result)
                self.assertIn('embedding_time_seconds', result)
                self.assertIn('search_results_count', result)
                self.assertIn('top_similarity', result)
                
                self.assertEqual(result['embedding_dimension'], 384)
                self.assertGreater(result['embedding_norm'], 0)
                self.assertGreater(result['embedding_time_seconds'], 0)
                self.assertEqual(result['search_results_count'], 3)
                self.assertEqual(result['top_similarity'], 0.95)


if __name__ == '__main__':
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestEmbeddingQualityAnalyzer))
    
    # Add integration tests (these require async support)
    integration_tests = loader.loadTestsFromTestCase(TestEmbeddingQualityIntegration)
    
    # Convert async tests to sync for unittest
    for test in integration_tests:
        if hasattr(test._testMethodName, 'test_') and 'async' in test._testMethodName:
            # Wrap async test methods
            original_method = getattr(test, test._testMethodName)
            if asyncio.iscoroutinefunction(original_method):
                setattr(test, test._testMethodName, 
                       lambda self, m=original_method: asyncio.run(m()))
    
    suite.addTests(integration_tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with error code if tests failed
    exit(0 if result.wasSuccessful() else 1)