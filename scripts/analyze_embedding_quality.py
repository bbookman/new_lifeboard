#!/usr/bin/env python3
"""
Embedding Quality Analysis Script

Comprehensive analysis of embedding quality issues including:
- Vector similarity score distributions
- Embedding dimension consistency
- Quality metrics and outlier detection
- Model performance comparison
- Semantic clustering analysis
"""

import sys
import os
import asyncio
import logging
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json
import sqlite3
from collections import defaultdict, Counter

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.database import DatabaseService
from core.vector_store import VectorStoreService
from core.embeddings import EmbeddingService
from config.models import AppConfig, EmbeddingConfig, VectorStoreConfig
from sources.limitless_processor import LimitlessProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/embedding_quality_analysis.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class EmbeddingQualityMetrics:
    """Container for embedding quality metrics"""
    total_embeddings: int
    dimension: int
    mean_norm: float
    std_norm: float
    norm_distribution: List[float]
    similarity_matrix: Optional[np.ndarray]
    outlier_count: int
    zero_vector_count: int
    duplicate_count: int
    content_type_distribution: Dict[str, int]
    namespace_distribution: Dict[str, int]
    quality_scores: Dict[str, float]


@dataclass
class ContentAnalysis:
    """Content quality analysis results"""
    content_length_stats: Dict[str, float]
    content_type_classification: Dict[str, List[str]]
    semantic_density_scores: List[float]
    preprocessing_quality: Dict[str, Any]


class EmbeddingQualityAnalyzer:
    """Comprehensive embedding quality analyzer"""
    
    def __init__(self):
        """Initialize the analyzer"""
        self.database = None
        self.vector_store = None
        self.embedding_service = None
        self.processor = LimitlessProcessor(enable_segmentation=True)
        
    async def initialize(self):
        """Initialize services"""
        try:
            logger.info("Initializing services for embedding quality analysis...")
            
            # Initialize database
            self.database = DatabaseService("data/lifeboard.db")
            logger.info("Database service initialized")
            
            # Initialize embedding service with default config
            embedding_config = EmbeddingConfig()
            self.embedding_service = EmbeddingService(embedding_config)
            await self.embedding_service.initialize()
            logger.info(f"Embedding service initialized with model: {embedding_config.model_name}")
            
            # Initialize vector store
            vector_config = VectorStoreConfig()
            self.vector_store = VectorStoreService(vector_config)
            logger.info("Vector store service initialized")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")
            return False
    
    async def analyze_embedding_quality(self) -> EmbeddingQualityMetrics:
        """Perform comprehensive embedding quality analysis"""
        logger.info("=== STARTING EMBEDDING QUALITY ANALYSIS ===")
        
        # Get all data from database
        db_stats = self.database.get_database_stats()
        logger.info(f"Database stats: {db_stats}")
        
        # Get vector store stats
        vector_stats = self.vector_store.get_stats()
        logger.info(f"Vector store stats: {vector_stats}")
        
        if vector_stats['total_vectors'] == 0:
            logger.warning("No vectors found in vector store!")
            return self._create_empty_metrics()
        
        # Analyze vector distributions
        vectors = self.vector_store.vectors
        embeddings_data = list(vectors.values())
        
        logger.info(f"Analyzing {len(embeddings_data)} embeddings...")
        
        # Calculate vector norms
        norms = [np.linalg.norm(vec) for vec in embeddings_data]
        mean_norm = np.mean(norms)
        std_norm = np.std(norms)
        
        logger.info(f"Vector norm statistics: mean={mean_norm:.4f}, std={std_norm:.4f}")
        
        # Detect outliers and quality issues
        outlier_count = self._count_outliers(norms)
        zero_vector_count = sum(1 for norm in norms if norm < 1e-6)
        duplicate_count = self._count_duplicates(embeddings_data)
        
        logger.info(f"Quality issues: {outlier_count} outliers, {zero_vector_count} zero vectors, {duplicate_count} duplicates")
        
        # Analyze content distribution
        content_analysis = await self._analyze_content_quality()
        
        # Calculate similarity matrix for sample
        sample_size = min(50, len(embeddings_data))
        sample_embeddings = embeddings_data[:sample_size]
        similarity_matrix = self._calculate_similarity_matrix(sample_embeddings)
        
        # Calculate quality scores
        quality_scores = self._calculate_quality_scores(
            embeddings_data, norms, content_analysis
        )
        
        return EmbeddingQualityMetrics(
            total_embeddings=len(embeddings_data),
            dimension=vector_stats['dimension'] or 0,
            mean_norm=mean_norm,
            std_norm=std_norm,
            norm_distribution=norms,
            similarity_matrix=similarity_matrix,
            outlier_count=outlier_count,
            zero_vector_count=zero_vector_count,
            duplicate_count=duplicate_count,
            content_type_distribution=content_analysis.content_type_classification.get('distribution', {}),
            namespace_distribution=db_stats.get('namespace_counts', {}),
            quality_scores=quality_scores
        )
    
    def _create_empty_metrics(self) -> EmbeddingQualityMetrics:
        """Create empty metrics when no data available"""
        return EmbeddingQualityMetrics(
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
    
    def _count_outliers(self, norms: List[float], threshold: float = 2.0) -> int:
        """Count outliers using z-score method"""
        if len(norms) < 3:
            return 0
            
        mean_norm = np.mean(norms)
        std_norm = np.std(norms)
        
        if std_norm < 1e-6:  # Nearly constant values
            return 0
        
        z_scores = [(norm - mean_norm) / std_norm for norm in norms]
        outliers = sum(1 for z in z_scores if abs(z) > threshold)
        
        return outliers
    
    def _count_duplicates(self, embeddings: List[np.ndarray], threshold: float = 0.99) -> int:
        """Count near-duplicate embeddings"""
        if len(embeddings) < 2:
            return 0
        
        duplicates = 0
        seen = set()
        
        for i, emb1 in enumerate(embeddings):
            emb1_tuple = tuple(emb1.round(6))  # Round for comparison
            if emb1_tuple in seen:
                duplicates += 1
            else:
                seen.add(emb1_tuple)
        
        return duplicates
    
    def _calculate_similarity_matrix(self, embeddings: List[np.ndarray]) -> np.ndarray:
        """Calculate similarity matrix for sample embeddings"""
        if len(embeddings) < 2:
            return np.array([[1.0]])
        
        n = len(embeddings)
        similarity_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i, n):
                if i == j:
                    similarity_matrix[i][j] = 1.0
                else:
                    sim = np.dot(embeddings[i], embeddings[j]) / (
                        np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])
                    )
                    similarity_matrix[i][j] = sim
                    similarity_matrix[j][i] = sim
        
        return similarity_matrix
    
    async def _analyze_content_quality(self) -> ContentAnalysis:
        """Analyze quality of content being embedded"""
        logger.info("Analyzing content quality...")
        
        # Get sample of data items
        with self.database.get_connection() as conn:
            cursor = conn.execute("""
                SELECT id, namespace, content, metadata, 
                       content_quality_score, semantic_density
                FROM data_items 
                ORDER BY updated_at DESC 
                LIMIT 500
            """)
            items = [dict(row) for row in cursor.fetchall()]
        
        if not items:
            logger.warning("No data items found for content analysis")
            return ContentAnalysis(
                content_length_stats={},
                content_type_classification={},
                semantic_density_scores=[],
                preprocessing_quality={}
            )
        
        # Analyze content lengths
        content_lengths = [len(item['content']) for item in items if item['content']]
        
        content_length_stats = {
            'mean': np.mean(content_lengths) if content_lengths else 0,
            'median': np.median(content_lengths) if content_lengths else 0,
            'std': np.std(content_lengths) if content_lengths else 0,
            'min': min(content_lengths) if content_lengths else 0,
            'max': max(content_lengths) if content_lengths else 0,
            'empty_count': sum(1 for item in items if not item['content'] or not item['content'].strip())
        }
        
        # Classify content types
        content_types = defaultdict(list)
        for item in items:
            content = item['content'] or ''
            namespace = item['namespace'] or 'unknown'
            
            # Simple heuristic classification
            if len(content) < 50:
                content_types['short'].append(namespace)
            elif 'conversation' in content.lower() or 'said' in content.lower():
                content_types['conversation'].append(namespace)
            elif any(word in content.lower() for word in ['question', 'answer', '?']):
                content_types['qa'].append(namespace)
            else:
                content_types['general'].append(namespace)
        
        # Convert to distribution
        type_distribution = {
            content_type: dict(Counter(namespaces)) 
            for content_type, namespaces in content_types.items()
        }
        
        # Analyze semantic density scores
        semantic_scores = [
            item['semantic_density'] for item in items 
            if item['semantic_density'] is not None
        ]
        
        # Analyze preprocessing quality
        preprocessing_quality = {
            'items_with_quality_scores': sum(1 for item in items if item['content_quality_score'] is not None),
            'items_with_semantic_density': len(semantic_scores),
            'avg_semantic_density': np.mean(semantic_scores) if semantic_scores else 0,
            'preprocessing_coverage': len([item for item in items if item['content_quality_score'] is not None]) / len(items) if items else 0
        }
        
        return ContentAnalysis(
            content_length_stats=content_length_stats,
            content_type_classification={
                'distribution': type_distribution,
                'summary': {ct: len(namespaces) for ct, namespaces in content_types.items()}
            },
            semantic_density_scores=semantic_scores,
            preprocessing_quality=preprocessing_quality
        )
    
    def _calculate_quality_scores(self, embeddings: List[np.ndarray], norms: List[float], 
                                content_analysis: ContentAnalysis) -> Dict[str, float]:
        """Calculate overall quality scores"""
        if not embeddings:
            return {}
        
        # Vector quality score (based on norm distribution)
        norm_consistency = 1.0 - (np.std(norms) / np.mean(norms)) if np.mean(norms) > 0 else 0
        vector_quality = max(0, min(1, norm_consistency))
        
        # Content quality score
        content_stats = content_analysis.content_length_stats
        avg_length = content_stats.get('mean', 0)
        empty_ratio = content_stats.get('empty_count', 0) / max(1, len(embeddings))
        content_quality = max(0, min(1, (avg_length / 1000) * (1 - empty_ratio)))
        
        # Preprocessing quality score
        preprocessing_coverage = content_analysis.preprocessing_quality.get('preprocessing_coverage', 0)
        
        # Overall quality score
        overall_quality = (vector_quality * 0.4 + content_quality * 0.4 + preprocessing_coverage * 0.2)
        
        return {
            'vector_quality': vector_quality,
            'content_quality': content_quality,
            'preprocessing_quality': preprocessing_coverage,
            'overall_quality': overall_quality
        }
    
    async def test_model_performance(self) -> Dict[str, Any]:
        """Test embedding model performance on sample queries"""
        logger.info("Testing embedding model performance...")
        
        test_queries = [
            "who is bruce",
            "tell me about peach",
            "what is the dog's name",
            "conversation with someone",
            "recent activities",
            "personal information"
        ]
        
        results = {}
        
        for query in test_queries:
            try:
                # Generate embedding
                start_time = datetime.now()
                embedding = await self.embedding_service.embed_text(query)
                end_time = datetime.now()
                
                # Calculate metrics
                embedding_time = (end_time - start_time).total_seconds()
                norm = np.linalg.norm(embedding)
                
                # Test search
                search_results = self.vector_store.search(embedding, k=5)
                
                results[query] = {
                    'embedding_dimension': len(embedding),
                    'embedding_norm': float(norm),
                    'embedding_time_seconds': embedding_time,
                    'search_results_count': len(search_results),
                    'top_similarity': search_results[0][1] if search_results else 0.0
                }
                
            except Exception as e:
                results[query] = {'error': str(e)}
        
        return results
    
    def generate_quality_report(self, metrics: EmbeddingQualityMetrics, 
                              performance_results: Dict[str, Any]) -> str:
        """Generate comprehensive quality report"""
        
        report_lines = [
            "=== EMBEDDING QUALITY ANALYSIS REPORT ===",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## VECTOR STORE STATISTICS",
            f"Total Embeddings: {metrics.total_embeddings:,}",
            f"Dimension: {metrics.dimension}",
            f"Mean Vector Norm: {metrics.mean_norm:.4f}",
            f"Std Vector Norm: {metrics.std_norm:.4f}",
            "",
            "## QUALITY ISSUES DETECTED",
            f"Outlier Vectors: {metrics.outlier_count} ({metrics.outlier_count/max(1,metrics.total_embeddings)*100:.1f}%)",
            f"Zero Vectors: {metrics.zero_vector_count} ({metrics.zero_vector_count/max(1,metrics.total_embeddings)*100:.1f}%)",
            f"Duplicate Vectors: {metrics.duplicate_count} ({metrics.duplicate_count/max(1,metrics.total_embeddings)*100:.1f}%)",
            "",
            "## QUALITY SCORES",
        ]
        
        for score_name, score_value in metrics.quality_scores.items():
            report_lines.append(f"{score_name.title().replace('_', ' ')}: {score_value:.3f}")
        
        report_lines.extend([
            "",
            "## NAMESPACE DISTRIBUTION",
        ])
        
        for namespace, count in sorted(metrics.namespace_distribution.items(), key=lambda x: x[1], reverse=True):
            percentage = count / max(1, metrics.total_embeddings) * 100
            report_lines.append(f"{namespace}: {count:,} ({percentage:.1f}%)")
        
        report_lines.extend([
            "",
            "## CONTENT TYPE DISTRIBUTION",
        ])
        
        for content_type, count in metrics.content_type_distribution.items():
            if isinstance(count, dict):
                total_count = sum(count.values()) if count else 0
                report_lines.append(f"{content_type}: {total_count}")
            elif isinstance(count, int):
                report_lines.append(f"{content_type}: {count}")
        
        report_lines.extend([
            "",
            "## MODEL PERFORMANCE TESTS",
        ])
        
        for query, result in performance_results.items():
            if 'error' in result:
                report_lines.append(f"Query: '{query}' - ERROR: {result['error']}")
            else:
                report_lines.extend([
                    f"Query: '{query}'",
                    f"  - Embedding Time: {result['embedding_time_seconds']:.3f}s",
                    f"  - Search Results: {result['search_results_count']}",
                    f"  - Top Similarity: {result['top_similarity']:.4f}",
                    f"  - Vector Norm: {result['embedding_norm']:.4f}",
                ])
        
        # Add recommendations
        report_lines.extend([
            "",
            "## RECOMMENDATIONS",
        ])
        
        recommendations = self._generate_recommendations(metrics)
        report_lines.extend(recommendations)
        
        return "\n".join(report_lines)
    
    def _generate_recommendations(self, metrics: EmbeddingQualityMetrics) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # Check overall quality
        overall_quality = metrics.quality_scores.get('overall_quality', 0)
        
        if overall_quality < 0.5:
            recommendations.append("⚠️  CRITICAL: Overall embedding quality is low")
        elif overall_quality < 0.7:
            recommendations.append("⚠️  WARNING: Embedding quality needs improvement")
        else:
            recommendations.append("✅ Good: Overall embedding quality is acceptable")
        
        # Vector-specific recommendations
        if metrics.zero_vector_count > metrics.total_embeddings * 0.05:  # >5% zero vectors
            recommendations.append("🔧 FIX: High number of zero vectors - check content preprocessing")
        
        if metrics.outlier_count > metrics.total_embeddings * 0.10:  # >10% outliers
            recommendations.append("🔧 FIX: High number of outlier vectors - review content normalization")
        
        if metrics.duplicate_count > metrics.total_embeddings * 0.15:  # >15% duplicates
            recommendations.append("🔧 FIX: High number of duplicate vectors - improve content deduplication")
        
        # Content-specific recommendations
        vector_quality = metrics.quality_scores.get('vector_quality', 0)
        if vector_quality < 0.6:
            recommendations.append("🔧 IMPROVE: Vector consistency is poor - consider different embedding model")
        
        content_quality = metrics.quality_scores.get('content_quality', 0)
        if content_quality < 0.5:
            recommendations.append("🔧 IMPROVE: Content quality is low - enhance preprocessing pipeline")
        
        preprocessing_quality = metrics.quality_scores.get('preprocessing_quality', 0)
        if preprocessing_quality < 0.5:
            recommendations.append("🔧 IMPROVE: Preprocessing coverage is incomplete - run full preprocessing")
        
        # Performance recommendations
        if metrics.total_embeddings == 0:
            recommendations.append("🚨 URGENT: No embeddings found - run embedding generation process")
        elif metrics.total_embeddings < 100:
            recommendations.append("📊 INFO: Low embedding count - consider ingesting more data")
        
        return recommendations
    
    def save_visualization_plots(self, metrics: EmbeddingQualityMetrics, output_dir: str = "logs"):
        """Generate and save visualization plots"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # Plot 1: Vector norm distribution
            if metrics.norm_distribution:
                plt.figure(figsize=(10, 6))
                plt.hist(metrics.norm_distribution, bins=50, alpha=0.7, edgecolor='black')
                plt.title('Vector Norm Distribution')
                plt.xlabel('Vector Norm')
                plt.ylabel('Frequency')
                plt.axvline(metrics.mean_norm, color='red', linestyle='--', label=f'Mean: {metrics.mean_norm:.4f}')
                plt.legend()
                plt.tight_layout()
                plt.savefig(f"{output_dir}/vector_norm_distribution.png", dpi=150)
                plt.close()
                logger.info(f"Saved vector norm distribution plot to {output_dir}/vector_norm_distribution.png")
            
            # Plot 2: Similarity matrix heatmap
            if metrics.similarity_matrix is not None and metrics.similarity_matrix.size > 1:
                plt.figure(figsize=(10, 8))
                sns.heatmap(metrics.similarity_matrix, annot=False, cmap='viridis', 
                           cbar_kws={'label': 'Cosine Similarity'})
                plt.title('Sample Embedding Similarity Matrix')
                plt.xlabel('Embedding Index')
                plt.ylabel('Embedding Index')
                plt.tight_layout()
                plt.savefig(f"{output_dir}/similarity_matrix.png", dpi=150)
                plt.close()
                logger.info(f"Saved similarity matrix plot to {output_dir}/similarity_matrix.png")
            
            # Plot 3: Quality scores radar chart
            if metrics.quality_scores:
                categories = list(metrics.quality_scores.keys())
                values = list(metrics.quality_scores.values())
                
                # Repeat first value to close the circle
                values += [values[0]]
                categories += [categories[0]]
                
                # Create angles for radar chart
                angles = [n / len(categories) * 2 * np.pi for n in range(len(categories))]
                
                fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
                ax.plot(angles, values, 'o-', linewidth=2, label='Quality Scores')
                ax.fill(angles, values, alpha=0.25)
                ax.set_xticks(angles[:-1])
                ax.set_xticklabels([cat.replace('_', ' ').title() for cat in categories[:-1]])
                ax.set_ylim(0, 1)
                plt.title('Embedding Quality Scores', size=16, y=1.1)
                plt.tight_layout()
                plt.savefig(f"{output_dir}/quality_scores_radar.png", dpi=150)
                plt.close()
                logger.info(f"Saved quality scores radar chart to {output_dir}/quality_scores_radar.png")
                
        except Exception as e:
            logger.error(f"Failed to generate visualization plots: {e}")


async def main():
    """Main analysis function"""
    logger.info("Starting embedding quality analysis...")
    
    # Create analyzer
    analyzer = EmbeddingQualityAnalyzer()
    
    # Initialize services
    if not await analyzer.initialize():
        logger.error("Failed to initialize analyzer services")
        return 1
    
    try:
        # Perform quality analysis
        logger.info("Performing embedding quality analysis...")
        metrics = await analyzer.analyze_embedding_quality()
        
        # Test model performance
        logger.info("Testing model performance...")
        performance_results = await analyzer.test_model_performance()
        
        # Generate report
        logger.info("Generating quality report...")
        report = analyzer.generate_quality_report(metrics, performance_results)
        
        # Save report
        os.makedirs("logs", exist_ok=True)
        report_path = "logs/embedding_quality_report.txt"
        with open(report_path, 'w') as f:
            f.write(report)
        
        logger.info(f"Quality report saved to: {report_path}")
        
        # Generate visualization plots
        logger.info("Generating visualization plots...")
        analyzer.save_visualization_plots(metrics)
        
        # Print summary to console
        print("\n" + "="*60)
        print("EMBEDDING QUALITY ANALYSIS SUMMARY")
        print("="*60)
        print(f"Total Embeddings: {metrics.total_embeddings:,}")
        print(f"Overall Quality Score: {metrics.quality_scores.get('overall_quality', 0):.3f}")
        print(f"Vector Quality: {metrics.quality_scores.get('vector_quality', 0):.3f}")
        print(f"Content Quality: {metrics.quality_scores.get('content_quality', 0):.3f}")
        print(f"Issues Found: {metrics.outlier_count + metrics.zero_vector_count + metrics.duplicate_count}")
        print(f"Full report saved to: {report_path}")
        print("="*60)
        
        return 0
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        return 1
    
    finally:
        # Cleanup
        if analyzer.embedding_service:
            analyzer.embedding_service.cleanup()


if __name__ == "__main__":
    exit(asyncio.run(main()))