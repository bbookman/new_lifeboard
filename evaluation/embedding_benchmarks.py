"""Embedding model benchmarking and evaluation framework."""

import time
import numpy as np
import json
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
import seaborn as sns

from core.logger import Logger
from core.database import DatabaseManager

logger = Logger(__name__)

@dataclass
class EmbeddingMetrics:
    """Container for embedding quality metrics."""
    model_name: str
    embedding_time: float
    dimension: int
    memory_usage_mb: float
    avg_similarity: float
    similarity_std: float
    silhouette_score: float
    retrieval_accuracy: float
    semantic_coherence: float
    computational_efficiency: float
    overall_score: float

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark tests."""
    test_sample_size: int = 100
    similarity_threshold: float = 0.7
    clustering_k: int = 5
    retrieval_top_k: int = 10
    evaluation_queries: List[str] = None
    
    def __post_init__(self):
        if self.evaluation_queries is None:
            self.evaluation_queries = [
                "What are the main topics discussed?",
                "How to improve productivity?",
                "Tell me about recent conversations",
                "What goals were mentioned?",
                "Any important deadlines or dates?",
                "Show me technical discussions",
                "What problems need solving?",
                "Recent project updates"
            ]

class EmbeddingBenchmarkFramework:
    """Framework for benchmarking and evaluating embedding models."""
    
    CANDIDATE_MODELS = {
        'all-MiniLM-L6-v2': {
            'dimension': 384,
            'description': 'Current lightweight model - fast but potentially less accurate',
            'pros': ['Fast inference', 'Low memory', 'Good for general purpose'],
            'cons': ['Lower accuracy', 'Limited semantic understanding']
        },
        'all-mpnet-base-v2': {
            'dimension': 768,
            'description': 'Microsoft MPNet - better semantic understanding',
            'pros': ['Better semantic understanding', 'Good performance on benchmarks'],
            'cons': ['Larger size', 'Slower inference']
        },
        'sentence-transformers/all-MiniLM-L12-v2': {
            'dimension': 384,
            'description': 'Larger MiniLM variant - balance of speed and accuracy',
            'pros': ['Better than L6', 'Still relatively fast', 'Good general performance'],
            'cons': ['Larger than L6', 'Still limited semantic depth']
        },
        'sentence-transformers/paraphrase-mpnet-base-v2': {
            'dimension': 768,
            'description': 'MPNet trained on paraphrases - excellent for semantic similarity',
            'pros': ['Excellent paraphrase detection', 'High semantic accuracy'],
            'cons': ['Slower inference', 'Higher memory usage']
        },
        'BAAI/bge-base-en-v1.5': {
            'dimension': 768,
            'description': 'BGE model - state-of-the-art performance',
            'pros': ['SOTA performance', 'Excellent retrieval', 'Good multilingual'],
            'cons': ['Largest model', 'Highest computational cost']
        }
    }
    
    def __init__(self, config: BenchmarkConfig = None):
        """Initialize benchmark framework.
        
        Args:
            config: Benchmark configuration
        """
        self.config = config or BenchmarkConfig()
        self.db_manager = DatabaseManager()
        self.results_dir = Path("evaluation/results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
    def load_test_data(self) -> List[Dict[str, Any]]:
        """Load test data from database.
        
        Returns:
            List of test data items
        """
        try:
            conn = self.db_manager._get_connection()
            cursor = conn.execute("""
                SELECT id, content, metadata, namespace
                FROM data_items 
                WHERE content IS NOT NULL 
                AND length(content) > 50
                ORDER BY RANDOM()
                LIMIT ?
            """, (self.config.test_sample_size,))
            
            test_data = []
            for row in cursor.fetchall():
                test_data.append({
                    'id': row[0],
                    'content': row[1],
                    'metadata': json.loads(row[2]) if row[2] else {},
                    'namespace': row[3]
                })
            
            logger.info(f"Loaded {len(test_data)} test items")
            return test_data
            
        except Exception as e:
            logger.error(f"Failed to load test data: {e}")
            return []
    
    def benchmark_model(self, model_name: str, test_data: List[Dict]) -> EmbeddingMetrics:
        """Benchmark a single embedding model.
        
        Args:
            model_name: Name of the model to benchmark
            test_data: Test data to use for evaluation
            
        Returns:
            Embedding metrics for the model
        """
        logger.info(f"Benchmarking model: {model_name}")
        
        try:
            # Load model
            start_time = time.time()
            model = SentenceTransformer(model_name)
            load_time = time.time() - start_time
            
            # Extract content for embedding
            contents = [item['content'] for item in test_data]
            
            # Generate embeddings
            embed_start = time.time()
            embeddings = model.encode(contents, show_progress_bar=True)
            embedding_time = time.time() - embed_start
            
            # Calculate metrics
            metrics = self._calculate_metrics(
                model_name=model_name,
                embeddings=embeddings,
                contents=contents,
                test_data=test_data,
                embedding_time=embedding_time,
                model=model
            )
            
            logger.info(f"Completed benchmarking {model_name}")
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to benchmark {model_name}: {e}")
            # Return default metrics with error indicators
            return EmbeddingMetrics(
                model_name=model_name,
                embedding_time=float('inf'),
                dimension=0,
                memory_usage_mb=0,
                avg_similarity=0,
                similarity_std=0,
                silhouette_score=0,
                retrieval_accuracy=0,
                semantic_coherence=0,
                computational_efficiency=0,
                overall_score=0
            )
    
    def _calculate_metrics(self, model_name: str, embeddings: np.ndarray, 
                          contents: List[str], test_data: List[Dict],
                          embedding_time: float, model: SentenceTransformer) -> EmbeddingMetrics:
        """Calculate comprehensive metrics for embedding quality.
        
        Args:
            model_name: Name of the model
            embeddings: Generated embeddings
            contents: Original content texts
            test_data: Original test data
            embedding_time: Time taken for embedding generation
            model: The embedding model instance
            
        Returns:
            Calculated metrics
        """
        # Basic metrics
        dimension = embeddings.shape[1]
        memory_usage_mb = embeddings.nbytes / (1024 * 1024)
        
        # Similarity metrics
        similarity_matrix = cosine_similarity(embeddings)
        # Remove diagonal (self-similarity)
        mask = np.ones(similarity_matrix.shape, dtype=bool)
        np.fill_diagonal(mask, False)
        similarities = similarity_matrix[mask]
        
        avg_similarity = np.mean(similarities)
        similarity_std = np.std(similarities)
        
        # Clustering quality
        silhouette = self._calculate_silhouette_score(embeddings)
        
        # Retrieval accuracy
        retrieval_accuracy = self._calculate_retrieval_accuracy(
            embeddings, contents, model
        )
        
        # Semantic coherence
        semantic_coherence = self._calculate_semantic_coherence(
            embeddings, contents, test_data
        )
        
        # Computational efficiency
        computational_efficiency = self._calculate_efficiency_score(
            embedding_time, len(contents), dimension
        )
        
        # Overall score (weighted combination)
        overall_score = self._calculate_overall_score(
            retrieval_accuracy, semantic_coherence, computational_efficiency,
            silhouette, avg_similarity
        )
        
        return EmbeddingMetrics(
            model_name=model_name,
            embedding_time=embedding_time,
            dimension=dimension,
            memory_usage_mb=memory_usage_mb,
            avg_similarity=avg_similarity,
            similarity_std=similarity_std,
            silhouette_score=silhouette,
            retrieval_accuracy=retrieval_accuracy,
            semantic_coherence=semantic_coherence,
            computational_efficiency=computational_efficiency,
            overall_score=overall_score
        )
    
    def _calculate_silhouette_score(self, embeddings: np.ndarray) -> float:
        """Calculate silhouette score for embedding clustering quality."""
        try:
            if len(embeddings) < self.config.clustering_k:
                return 0.0
                
            kmeans = KMeans(n_clusters=self.config.clustering_k, random_state=42)
            labels = kmeans.fit_predict(embeddings)
            return silhouette_score(embeddings, labels)
        except Exception as e:
            logger.warning(f"Failed to calculate silhouette score: {e}")
            return 0.0
    
    def _calculate_retrieval_accuracy(self, embeddings: np.ndarray, 
                                    contents: List[str], model: SentenceTransformer) -> float:
        """Calculate retrieval accuracy using evaluation queries."""
        try:
            total_score = 0.0
            
            for query in self.config.evaluation_queries:
                query_embedding = model.encode([query])[0]
                
                # Calculate similarities
                similarities = cosine_similarity([query_embedding], embeddings)[0]
                
                # Get top-k results
                top_k_indices = np.argsort(similarities)[-self.config.retrieval_top_k:][::-1]
                
                # Score based on relevance (simplified - could be enhanced)
                query_score = 0.0
                for idx in top_k_indices:
                    if similarities[idx] > self.config.similarity_threshold:
                        query_score += similarities[idx]
                
                total_score += query_score / len(top_k_indices)
            
            return total_score / len(self.config.evaluation_queries)
            
        except Exception as e:
            logger.warning(f"Failed to calculate retrieval accuracy: {e}")
            return 0.0
    
    def _calculate_semantic_coherence(self, embeddings: np.ndarray, 
                                    contents: List[str], test_data: List[Dict]) -> float:
        """Calculate semantic coherence based on content relationships."""
        try:
            # Group by namespace to check if similar content clusters together
            namespace_groups = {}
            for i, item in enumerate(test_data):
                namespace = item.get('namespace', 'default')
                if namespace not in namespace_groups:
                    namespace_groups[namespace] = []
                namespace_groups[namespace].append(i)
            
            if len(namespace_groups) < 2:
                return 0.5  # Default score if no meaningful grouping
            
            # Calculate intra vs inter-group similarities
            intra_similarities = []
            inter_similarities = []
            
            for ns1, indices1 in namespace_groups.items():
                if len(indices1) < 2:
                    continue
                    
                # Intra-group similarities
                for i in range(len(indices1)):
                    for j in range(i + 1, len(indices1)):
                        idx1, idx2 = indices1[i], indices1[j]
                        sim = cosine_similarity([embeddings[idx1]], [embeddings[idx2]])[0][0]
                        intra_similarities.append(sim)
                
                # Inter-group similarities
                for ns2, indices2 in namespace_groups.items():
                    if ns1 >= ns2:  # Avoid duplicates
                        continue
                    for idx1 in indices1[:5]:  # Limit for efficiency
                        for idx2 in indices2[:5]:
                            sim = cosine_similarity([embeddings[idx1]], [embeddings[idx2]])[0][0]
                            inter_similarities.append(sim)
            
            if not intra_similarities or not inter_similarities:
                return 0.5
            
            avg_intra = np.mean(intra_similarities)
            avg_inter = np.mean(inter_similarities)
            
            # Higher score if intra-group similarity > inter-group similarity
            coherence = max(0, (avg_intra - avg_inter) / (avg_intra + avg_inter + 1e-10))
            return coherence
            
        except Exception as e:
            logger.warning(f"Failed to calculate semantic coherence: {e}")
            return 0.0
    
    def _calculate_efficiency_score(self, embedding_time: float, 
                                  num_items: int, dimension: int) -> float:
        """Calculate computational efficiency score."""
        try:
            # Time per item
            time_per_item = embedding_time / num_items
            
            # Normalize based on dimension (higher dimension expected to be slower)
            dimension_factor = dimension / 768  # Normalize to 768d baseline
            normalized_time = time_per_item / dimension_factor
            
            # Convert to efficiency score (lower time = higher score)
            # Use sigmoid to cap at 1.0
            efficiency = 1 / (1 + normalized_time * 10)
            return efficiency
            
        except Exception as e:
            logger.warning(f"Failed to calculate efficiency score: {e}")
            return 0.0
    
    def _calculate_overall_score(self, retrieval_accuracy: float, 
                               semantic_coherence: float, computational_efficiency: float,
                               silhouette_score: float, avg_similarity: float) -> float:
        """Calculate weighted overall score."""
        # Weights for different aspects
        weights = {
            'retrieval': 0.3,
            'coherence': 0.25,
            'efficiency': 0.2,
            'clustering': 0.15,
            'similarity': 0.1
        }
        
        # Normalize silhouette score (can be negative)
        normalized_silhouette = (silhouette_score + 1) / 2
        
        overall = (
            weights['retrieval'] * retrieval_accuracy +
            weights['coherence'] * semantic_coherence +
            weights['efficiency'] * computational_efficiency +
            weights['clustering'] * normalized_silhouette +
            weights['similarity'] * avg_similarity
        )
        
        return overall
    
    def run_full_benchmark(self, models_to_test: List[str] = None) -> Dict[str, EmbeddingMetrics]:
        """Run comprehensive benchmark on all specified models.
        
        Args:
            models_to_test: List of model names to test. If None, tests all candidates.
            
        Returns:
            Dictionary mapping model names to their metrics
        """
        if models_to_test is None:
            models_to_test = list(self.CANDIDATE_MODELS.keys())
        
        logger.info(f"Starting full benchmark for {len(models_to_test)} models")
        
        # Load test data
        test_data = self.load_test_data()
        if not test_data:
            logger.error("No test data available for benchmarking")
            return {}
        
        results = {}
        
        for model_name in models_to_test:
            try:
                logger.info(f"Testing model: {model_name}")
                metrics = self.benchmark_model(model_name, test_data)
                results[model_name] = metrics
                
                # Save individual results
                self._save_metrics(metrics)
                
            except Exception as e:
                logger.error(f"Failed to benchmark {model_name}: {e}")
                continue
        
        # Generate comparison report
        self._generate_comparison_report(results)
        
        logger.info("Full benchmark completed")
        return results
    
    def _save_metrics(self, metrics: EmbeddingMetrics) -> None:
        """Save metrics to JSON file."""
        try:
            filename = f"{metrics.model_name.replace('/', '_')}_metrics.json"
            filepath = self.results_dir / filename
            
            with open(filepath, 'w') as f:
                json.dump(asdict(metrics), f, indent=2)
                
            logger.info(f"Saved metrics for {metrics.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def _generate_comparison_report(self, results: Dict[str, EmbeddingMetrics]) -> None:
        """Generate comprehensive comparison report."""
        try:
            # Create comparison table
            report_lines = [
                "# Embedding Model Benchmark Results",
                "",
                "## Summary",
                ""
            ]
            
            # Sort by overall score
            sorted_results = sorted(results.items(), 
                                  key=lambda x: x[1].overall_score, reverse=True)
            
            # Add rankings
            report_lines.append("### Model Rankings (by Overall Score)")
            report_lines.append("")
            for i, (model_name, metrics) in enumerate(sorted_results, 1):
                report_lines.append(f"{i}. **{model_name}** - Score: {metrics.overall_score:.3f}")
            report_lines.append("")
            
            # Add detailed comparison table
            report_lines.append("### Detailed Metrics")
            report_lines.append("")
            
            header = "| Model | Overall | Retrieval | Coherence | Efficiency | Time (s) | Dimension |"
            separator = "|-------|---------|-----------|-----------|------------|----------|-----------|"
            
            report_lines.append(header)
            report_lines.append(separator)
            
            for model_name, metrics in sorted_results:
                row = (f"| {model_name} | {metrics.overall_score:.3f} | "
                      f"{metrics.retrieval_accuracy:.3f} | {metrics.semantic_coherence:.3f} | "
                      f"{metrics.computational_efficiency:.3f} | {metrics.embedding_time:.2f} | "
                      f"{metrics.dimension} |")
                report_lines.append(row)
            
            # Add recommendations
            report_lines.extend([
                "",
                "## Recommendations",
                ""
            ])
            
            if sorted_results:
                best_model = sorted_results[0][0]
                best_metrics = sorted_results[0][1]
                
                report_lines.append(f"### Best Overall: {best_model}")
                report_lines.append(f"- Overall Score: {best_metrics.overall_score:.3f}")
                report_lines.append(f"- Retrieval Accuracy: {best_metrics.retrieval_accuracy:.3f}")
                report_lines.append(f"- Embedding Time: {best_metrics.embedding_time:.2f}s")
                report_lines.append("")
                
                # Find fastest model
                fastest_model = min(results.items(), key=lambda x: x[1].embedding_time)
                if fastest_model[0] != best_model:
                    report_lines.append(f"### Fastest: {fastest_model[0]}")
                    report_lines.append(f"- Embedding Time: {fastest_model[1].embedding_time:.2f}s")
                    report_lines.append(f"- Overall Score: {fastest_model[1].overall_score:.3f}")
                    report_lines.append("")
                
                # Find most accurate for retrieval
                most_accurate = max(results.items(), key=lambda x: x[1].retrieval_accuracy)
                if most_accurate[0] != best_model:
                    report_lines.append(f"### Most Accurate: {most_accurate[0]}")
                    report_lines.append(f"- Retrieval Accuracy: {most_accurate[1].retrieval_accuracy:.3f}")
                    report_lines.append(f"- Overall Score: {most_accurate[1].overall_score:.3f}")
            
            # Save report
            report_path = self.results_dir / "benchmark_report.md"
            with open(report_path, 'w') as f:
                f.write('\n'.join(report_lines))
            
            logger.info(f"Comparison report saved to: {report_path}")
            
        except Exception as e:
            logger.error(f"Failed to generate comparison report: {e}")
    
    def create_visualizations(self, results: Dict[str, EmbeddingMetrics]) -> None:
        """Create visualization charts for benchmark results."""
        try:
            # Set up the plotting style
            plt.style.use('seaborn-v0_8')
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle('Embedding Model Benchmark Results', fontsize=16)
            
            models = list(results.keys())
            
            # Overall scores
            overall_scores = [results[model].overall_score for model in models]
            axes[0, 0].bar(range(len(models)), overall_scores)
            axes[0, 0].set_title('Overall Scores')
            axes[0, 0].set_xticks(range(len(models)))
            axes[0, 0].set_xticklabels([m.split('/')[-1] for m in models], rotation=45)
            
            # Retrieval accuracy vs efficiency
            retrieval_scores = [results[model].retrieval_accuracy for model in models]
            efficiency_scores = [results[model].computational_efficiency for model in models]
            
            axes[0, 1].scatter(efficiency_scores, retrieval_scores)
            for i, model in enumerate(models):
                axes[0, 1].annotate(model.split('/')[-1], 
                                   (efficiency_scores[i], retrieval_scores[i]))
            axes[0, 1].set_xlabel('Computational Efficiency')
            axes[0, 1].set_ylabel('Retrieval Accuracy')
            axes[0, 1].set_title('Efficiency vs Accuracy')
            
            # Embedding times
            embedding_times = [results[model].embedding_time for model in models]
            axes[1, 0].bar(range(len(models)), embedding_times)
            axes[1, 0].set_title('Embedding Times')
            axes[1, 0].set_xticks(range(len(models)))
            axes[1, 0].set_xticklabels([m.split('/')[-1] for m in models], rotation=45)
            axes[1, 0].set_ylabel('Time (seconds)')
            
            # Metric comparison radar-like
            metrics_data = []
            metric_names = ['Retrieval', 'Coherence', 'Efficiency', 'Overall']
            
            for model in models:
                model_metrics = [
                    results[model].retrieval_accuracy,
                    results[model].semantic_coherence,
                    results[model].computational_efficiency,
                    results[model].overall_score
                ]
                metrics_data.append(model_metrics)
            
            x = np.arange(len(metric_names))
            width = 0.8 / len(models)
            
            for i, (model, data) in enumerate(zip(models, metrics_data)):
                axes[1, 1].bar(x + i * width, data, width, 
                              label=model.split('/')[-1], alpha=0.8)
            
            axes[1, 1].set_xlabel('Metrics')
            axes[1, 1].set_ylabel('Score')
            axes[1, 1].set_title('Metric Comparison')
            axes[1, 1].set_xticks(x + width * len(models) / 2)
            axes[1, 1].set_xticklabels(metric_names)
            axes[1, 1].legend()
            
            plt.tight_layout()
            
            # Save visualization
            viz_path = self.results_dir / "benchmark_visualization.png"
            plt.savefig(viz_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            logger.info(f"Visualization saved to: {viz_path}")
            
        except Exception as e:
            logger.error(f"Failed to create visualizations: {e}")


def main():
    """Main function to run embedding benchmarks."""
    print("🚀 Starting Embedding Model Benchmarks...")
    
    # Configuration
    config = BenchmarkConfig(
        test_sample_size=50,  # Start with smaller sample for testing
        similarity_threshold=0.7
    )
    
    framework = EmbeddingBenchmarkFramework(config)
    
    # Test a subset first
    test_models = [
        'all-MiniLM-L6-v2',  # Current model
        'all-mpnet-base-v2',  # Better alternative
        'BAAI/bge-base-en-v1.5'  # SOTA model
    ]
    
    results = framework.run_full_benchmark(test_models)
    
    if results:
        framework.create_visualizations(results)
        
        print("📊 Benchmark Results Summary:")
        sorted_results = sorted(results.items(), 
                              key=lambda x: x[1].overall_score, reverse=True)
        
        for i, (model, metrics) in enumerate(sorted_results, 1):
            print(f"{i}. {model}")
            print(f"   Overall Score: {metrics.overall_score:.3f}")
            print(f"   Retrieval Accuracy: {metrics.retrieval_accuracy:.3f}")
            print(f"   Embedding Time: {metrics.embedding_time:.2f}s")
            print()
        
        print("✅ Benchmark completed! Check evaluation/results/ for detailed reports.")
    else:
        print("❌ No benchmark results generated.")


if __name__ == "__main__":
    main()