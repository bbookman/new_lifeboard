#!/usr/bin/env python3
"""
Temporary Data Cleaning Pipeline Demonstration Script

This script demonstrates the data cleaning pipeline using realistic "before" data
that contains duplicates and near-duplicates, then shows the transformation through
each cleaning step with detailed BEFORE/AFTER reporting.
"""

import sys
import os
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# Add the project root to path so we can import the pipeline components
project_root = "/Users/brucebookman/code/new_lifeboard"
sys.path.insert(0, project_root)

from sources.base import DataItem
from sources.limitless_processor import (
    LimitlessProcessor, 
    BasicCleaningProcessor,
    MetadataEnrichmentProcessor,
    ConversationSegmentProcessor,
    MarkdownProcessor,
    DeduplicationProcessor
)
from sources.semantic_deduplication_processor import SemanticDeduplicationProcessor
from core.embeddings import EmbeddingService
from config.factory import ConfigFactory

class DataCleaningDemo:
    """Demonstrates the data cleaning pipeline with detailed reporting"""
    
    def __init__(self):
        self.test_data = None
        self.pipeline_results = []
        
    def generate_test_data(self) -> Dict[str, Any]:
        """Generate realistic test data mimicking Limitless API response with intentional duplicates"""
        
        # Create realistic conversation data with lots of duplication and near-duplication
        # This mimics the kind of redundancy found in real transcripts
        test_lifelog = {
            "id": "demo_conversation_001",
            "title": "Team Planning Meeting - Project Discussion",
            "startTime": "2024-08-20T10:00:00Z",
            "endTime": "2024-08-20T10:45:00Z",
            "isStarred": False,
            "updatedAt": "2024-08-20T10:45:15Z",
            "markdown": "# Team Planning Meeting\n\nDiscussion about project timeline and deliverables...",
            "contents": [
                # Meeting opening with typical redundancy
                {
                    "type": "blockquote",
                    "content": "Good morning everyone, thanks for joining the meeting",
                    "speakerName": "Sarah",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:00:05Z"
                },
                {
                    "type": "blockquote", 
                    "content": "Good morning, thanks for having us",
                    "speakerName": "Mike",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:00:08Z"
                },
                {
                    "type": "blockquote",
                    "content": "Morning everyone, glad to be here",
                    "speakerName": "Alex",
                    "speakerIdentifier": "user",
                    "startTime": "2024-08-20T10:00:12Z"
                },
                
                # Agreement patterns - very common in conversations
                {
                    "type": "blockquote",
                    "content": "Yeah, that's right",
                    "speakerName": "Mike",
                    "speakerIdentifier": "other", 
                    "startTime": "2024-08-20T10:05:22Z"
                },
                {
                    "type": "blockquote",
                    "content": "That's right, yeah",
                    "speakerName": "Sarah",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:05:45Z"
                },
                {
                    "type": "blockquote",
                    "content": "Exactly, that's correct",
                    "speakerName": "Alex",
                    "speakerIdentifier": "user",
                    "startTime": "2024-08-20T10:06:12Z"
                },
                {
                    "type": "blockquote",
                    "content": "Yes, that's absolutely right",
                    "speakerName": "Mike",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:06:33Z"
                },
                
                # Project discussion with similar sentiments
                {
                    "type": "blockquote",
                    "content": "I think we need to focus on the deadline",
                    "speakerName": "Sarah",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:10:15Z"
                },
                {
                    "type": "blockquote",
                    "content": "The deadline is really important to keep in mind",
                    "speakerName": "Mike", 
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:10:42Z"
                },
                {
                    "type": "blockquote",
                    "content": "We definitely need to watch that deadline closely",
                    "speakerName": "Alex",
                    "speakerIdentifier": "user",
                    "startTime": "2024-08-20T10:11:08Z"
                },
                
                # Good point variations - extremely common
                {
                    "type": "blockquote", 
                    "content": "That's a good point",
                    "speakerName": "Alex",
                    "speakerIdentifier": "user",
                    "startTime": "2024-08-20T10:15:22Z"
                },
                {
                    "type": "blockquote",
                    "content": "That's a really good point",
                    "speakerName": "Sarah",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:18:45Z"
                },
                {
                    "type": "blockquote",
                    "content": "Good point, I agree",
                    "speakerName": "Mike",
                    "speakerIdentifier": "other", 
                    "startTime": "2024-08-20T10:19:12Z"
                },
                {
                    "type": "blockquote",
                    "content": "Yeah, that's a great point",
                    "speakerName": "Alex",
                    "speakerIdentifier": "user",
                    "startTime": "2024-08-20T10:22:33Z"
                },
                
                # Resource concerns with similar wording
                {
                    "type": "blockquote",
                    "content": "We might need more resources for this",
                    "speakerName": "Sarah",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:25:15Z"
                },
                {
                    "type": "blockquote",
                    "content": "I think we need additional resources", 
                    "speakerName": "Mike",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:25:42Z"
                },
                {
                    "type": "blockquote",
                    "content": "More resources would definitely help",
                    "speakerName": "Alex",
                    "speakerIdentifier": "user",
                    "startTime": "2024-08-20T10:26:08Z"
                },
                
                # Filler content with whitespace issues and redundancy
                {
                    "type": "blockquote",
                    "content": "  Um,  I think that's    the best approach   ",
                    "speakerName": "Mike",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:30:22Z"
                },
                {
                    "type": "blockquote", 
                    "content": "Yeah, that approach sounds good to me\t\n",
                    "speakerName": "Sarah",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:30:45Z"
                },
                {
                    "type": "blockquote",
                    "content": "I agree, that's probably the best way to go",
                    "speakerName": "Alex",
                    "speakerIdentifier": "user", 
                    "startTime": "2024-08-20T10:31:12Z"
                },
                
                # Meeting wrap-up redundancy
                {
                    "type": "blockquote",
                    "content": "Thanks everyone, this was productive",
                    "speakerName": "Sarah",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:42:15Z"
                },
                {
                    "type": "blockquote",
                    "content": "Yes, really productive meeting, thanks",
                    "speakerName": "Mike",
                    "speakerIdentifier": "other",
                    "startTime": "2024-08-20T10:42:42Z"
                },
                {
                    "type": "blockquote",
                    "content": "Great meeting, very productive, thank you",
                    "speakerName": "Alex",
                    "speakerIdentifier": "user",
                    "startTime": "2024-08-20T10:43:08Z"
                }
            ]
        }
        
        # Create DataItem from the test data
        test_item = DataItem(
            namespace="demo",
            source_id="conversation_001", 
            content=self._extract_raw_content(test_lifelog),
            metadata={"original_lifelog": test_lifelog},
            created_at=datetime.fromisoformat("2024-08-20T10:00:00+00:00"),
            updated_at=datetime.fromisoformat("2024-08-20T10:45:15+00:00")
        )
        
        self.test_data = test_item
        return test_lifelog
        
    def _extract_raw_content(self, lifelog: Dict[str, Any]) -> str:
        """Extract raw content from lifelog contents for display purposes"""
        content_parts = []
        
        for node in lifelog.get("contents", []):
            if node.get("content"):
                speaker = node.get("speakerName", "Unknown")
                if node.get("speakerIdentifier") == "user":
                    speaker = f"{speaker} (You)"
                content_parts.append(f"{speaker}: {node['content']}")
                
        return "\n".join(content_parts)

    async def run_cleaning_pipeline(self) -> List[Dict[str, Any]]:
        """Run the complete cleaning pipeline and track results at each step"""
        
        if not self.test_data:
            raise ValueError("Test data not generated. Call generate_test_data() first.")
            
        results = []
        current_item = self.test_data
        
        # Step 1: Show raw data
        raw_content = current_item.content
        raw_metadata = dict(current_item.metadata)
        
        results.append({
            "step": "Raw Data",
            "processor": "None",
            "before_content": raw_content,
            "after_content": raw_content,
            "before_metadata": raw_metadata,
            "after_metadata": raw_metadata,
            "changes": "Original unprocessed data",
            "effect": f"Starting with {len(raw_content.split())} words across {len(raw_content.splitlines())} lines"
        })
        
        # Step 2: Basic Cleaning
        processor = BasicCleaningProcessor()
        before_content = current_item.content
        before_metadata = dict(current_item.metadata)
        current_item = processor.process(current_item)
        
        results.append({
            "step": "Basic Cleaning",
            "processor": "BasicCleaningProcessor", 
            "before_content": before_content,
            "after_content": current_item.content,
            "before_metadata": before_metadata,
            "after_metadata": dict(current_item.metadata),
            "changes": "Normalized whitespace, removed control characters",
            "effect": self._calculate_text_effect(before_content, current_item.content)
        })
        
        # Step 3: Metadata Enrichment
        processor = MetadataEnrichmentProcessor()
        before_content = current_item.content
        before_metadata = dict(current_item.metadata)
        current_item = processor.process(current_item)
        
        results.append({
            "step": "Metadata Enrichment",
            "processor": "MetadataEnrichmentProcessor",
            "before_content": before_content,
            "after_content": current_item.content,
            "before_metadata": before_metadata,
            "after_metadata": dict(current_item.metadata),
            "changes": "Added content statistics, conversation metadata, time analysis",
            "effect": self._calculate_metadata_effect(before_metadata, current_item.metadata)
        })
        
        # Step 4: Conversation Segmentation
        processor = ConversationSegmentProcessor()
        before_content = current_item.content
        before_metadata = dict(current_item.metadata)
        current_item = processor.process(current_item)
        
        results.append({
            "step": "Conversation Segmentation",
            "processor": "ConversationSegmentProcessor",
            "before_content": before_content,
            "after_content": current_item.content,
            "before_metadata": before_metadata,
            "after_metadata": dict(current_item.metadata),
            "changes": "Analyzed conversation structure for segmentation",
            "effect": self._calculate_segmentation_effect(before_metadata, current_item.metadata)
        })
        
        # Step 5: Markdown Generation
        processor = MarkdownProcessor()
        before_content = current_item.content
        before_metadata = dict(current_item.metadata)
        current_item = processor.process(current_item)
        
        results.append({
            "step": "Markdown Generation",
            "processor": "MarkdownProcessor",
            "before_content": before_content, 
            "after_content": current_item.content,
            "before_metadata": before_metadata,
            "after_metadata": dict(current_item.metadata),
            "changes": "Generated cleaned markdown representation",
            "effect": self._calculate_markdown_effect(before_metadata, current_item.metadata)
        })
        
        # Step 6: Semantic Deduplication (the big one!)
        try:
            # Initialize embedding service for semantic processing
            config = ConfigFactory.create_config()
            embedding_service = EmbeddingService(config.embeddings)
            
            processor = SemanticDeduplicationProcessor(
                similarity_threshold=0.85,
                min_line_words=3,
                enable_cross_speaker_clustering=True,
                embedding_service=embedding_service
            )
            
            before_content = current_item.content
            before_metadata = dict(current_item.metadata)
            
            # For semantic deduplication, we need to use batch processing
            processed_items = await processor.process_batch([current_item])
            current_item = processed_items[0] if processed_items else current_item
            
            results.append({
                "step": "Semantic Deduplication",
                "processor": "SemanticDeduplicationProcessor",
                "before_content": before_content,
                "after_content": current_item.content,
                "before_metadata": before_metadata,
                "after_metadata": dict(current_item.metadata),
                "changes": "Grouped semantically similar lines, selected canonical representations",
                "effect": self._calculate_semantic_effect(before_metadata, current_item.metadata)
            })
            
        except Exception as e:
            # Fallback to basic deduplication if semantic processing fails
            processor = DeduplicationProcessor()
            before_content = current_item.content
            before_metadata = dict(current_item.metadata)
            current_item = processor.process(current_item)
            
            results.append({
                "step": "Basic Deduplication (Fallback)",
                "processor": "DeduplicationProcessor",
                "before_content": before_content,
                "after_content": current_item.content,
                "before_metadata": before_metadata,
                "after_metadata": dict(current_item.metadata),
                "changes": f"Basic deduplication analysis (semantic processing failed: {e})",
                "effect": "Added content hash for deduplication tracking"
            })
        
        self.pipeline_results = results
        return results
        
    def _calculate_text_effect(self, before: str, after: str) -> str:
        """Calculate the effect of text cleaning"""
        before_chars = len(before)
        after_chars = len(after)
        char_diff = before_chars - after_chars
        
        before_words = len(before.split())
        after_words = len(after.split())
        
        if char_diff > 0:
            return f"Reduced {before_chars} chars to {after_chars} chars (-{char_diff}), words unchanged: {before_words}"
        else:
            return f"Character count stable: {after_chars} chars, {after_words} words"
    
    def _calculate_metadata_effect(self, before: Dict, after: Dict) -> str:
        """Calculate the effect of metadata enrichment"""
        before_keys = len(before.keys())
        after_keys = len(after.keys())
        new_keys = after_keys - before_keys
        
        # Look for specific enrichments
        enrichments = []
        if 'content_stats' in after and 'content_stats' not in before:
            enrichments.append("content statistics")
        if 'conversation_metadata' in after and 'conversation_metadata' not in before:
            enrichments.append("conversation metadata")
        if 'duration_seconds' in after and 'duration_seconds' not in before:
            enrichments.append("duration analysis")
            
        return f"Added {new_keys} metadata fields: {', '.join(enrichments) if enrichments else 'processing history'}"
    
    def _calculate_segmentation_effect(self, before: Dict, after: Dict) -> str:
        """Calculate the effect of conversation segmentation"""
        segmentation = after.get('segmentation', {})
        if segmentation.get('is_segmented'):
            return f"Segmented into {segmentation.get('total_segments', 1)} parts"
        else:
            word_count = segmentation.get('word_count', 0)
            return f"No segmentation needed (content length: {word_count} words)"
    
    def _calculate_markdown_effect(self, before: Dict, after: Dict) -> str:
        """Calculate the effect of markdown generation"""
        if 'cleaned_markdown' in after and 'cleaned_markdown' not in before:
            return "Generated formatted markdown representation for display"
        return "Markdown processing completed"
    
    def _calculate_semantic_effect(self, before: Dict, after: Dict) -> str:
        """Calculate the effect of semantic deduplication"""
        semantic_metadata = after.get('semantic_metadata', {})
        
        if semantic_metadata.get('processed'):
            total_lines = semantic_metadata.get('total_lines_analyzed', 0)
            clustered_lines = semantic_metadata.get('clustered_lines', 0)
            clusters_found = semantic_metadata.get('clusters_found', 0)
            semantic_density = semantic_metadata.get('semantic_density', 1.0)
            
            reduction_percent = int((1 - semantic_density) * 100)
            
            return (f"Analyzed {total_lines} lines, found {clusters_found} semantic clusters, "
                   f"reduced to {clustered_lines} canonical representations "
                   f"({reduction_percent}% reduction in conversation length)")
        else:
            return "Semantic deduplication analysis completed (no clusters formed)"

    def generate_report(self) -> str:
        """Generate a detailed BEFORE/AFTER report showing the effects of each cleaning step"""
        
        if not self.pipeline_results:
            return "No pipeline results available. Run run_cleaning_pipeline() first."
            
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("DATA CLEANING PIPELINE DEMONSTRATION")
        report_lines.append("=" * 80)
        report_lines.append("")
        
        for i, result in enumerate(self.pipeline_results, 1):
            report_lines.append(f"STEP {i}: {result['step'].upper()}")
            report_lines.append("-" * 60)
            
            # Show processor used
            if result['processor'] != "None":
                report_lines.append(f"PROCESSOR: {result['processor']}")
                report_lines.append("")
            
            # Special handling for semantic deduplication step
            if 'Semantic' in result['step']:
                self._add_semantic_deduplication_details(report_lines, result)
            else:
                # Regular BEFORE/AFTER for other steps
                # Show BEFORE content (truncated for readability)
                before_content = result['before_content']
                if len(before_content) > 200:
                    before_preview = before_content[:200] + "... [truncated]"
                else:
                    before_preview = before_content
                    
                report_lines.append("BEFORE:")
                for line in before_preview.split('\n'):
                    report_lines.append(f"  {line}")
                report_lines.append("")
                
                # Show AFTER content (truncated for readability)
                after_content = result['after_content']
                if len(after_content) > 200:
                    after_preview = after_content[:200] + "... [truncated]"
                else:
                    after_preview = after_content
                    
                report_lines.append("AFTER:")
                for line in after_preview.split('\n'):
                    report_lines.append(f"  {line}")
                report_lines.append("")
            
            # Show process and effect
            report_lines.append(f"PROCESS: {result['changes']}")
            report_lines.append(f"EFFECT: {result['effect']}")
            
            # Show metadata changes for key steps
            if result['step'] in ['Metadata Enrichment', 'Semantic Deduplication']:
                report_lines.append("")
                report_lines.append("METADATA CHANGES:")
                self._add_metadata_diff(report_lines, result['before_metadata'], result['after_metadata'])
                
            report_lines.append("")
            report_lines.append("=" * 60)
            report_lines.append("")
        
        # Add summary
        report_lines.append("PIPELINE SUMMARY")
        report_lines.append("-" * 40)
        
        first_result = self.pipeline_results[0]
        last_result = self.pipeline_results[-1]
        
        original_lines = len(first_result['before_content'].splitlines())
        final_lines = len(last_result['after_content'].splitlines())
        
        original_words = len(first_result['before_content'].split())
        final_words = len(last_result['after_content'].split())
        
        report_lines.append(f"Original conversation: {original_lines} lines, {original_words} words")
        report_lines.append(f"Final processed result: {final_lines} lines, {final_words} words")
        
        # Look for semantic deduplication results
        semantic_result = None
        for result in self.pipeline_results:
            if 'Semantic' in result['step']:
                semantic_result = result
                break
                
        if semantic_result:
            semantic_metadata = semantic_result['after_metadata'].get('semantic_metadata', {})
            if semantic_metadata.get('processed'):
                clusters = semantic_metadata.get('clusters_found', 0)
                density = semantic_metadata.get('semantic_density', 1.0)
                reduction = int((1 - density) * 100)
                
                report_lines.append(f"Semantic clusters found: {clusters}")
                report_lines.append(f"Conversation compression: {reduction}% reduction through deduplication")
        
        report_lines.append("")
        report_lines.append("=" * 80)
        
        return "\n".join(report_lines)
    
    def _add_metadata_diff(self, report_lines: List[str], before: Dict, after: Dict) -> None:
        """Add metadata differences to report"""
        
        # Show new keys added
        before_keys = set(before.keys())
        after_keys = set(after.keys())
        new_keys = after_keys - before_keys
        
        if new_keys:
            report_lines.append("  New metadata added:")
            for key in sorted(new_keys):
                if key == 'semantic_metadata':
                    semantic = after[key]
                    if semantic.get('processed'):
                        report_lines.append(f"    {key}: {semantic.get('clusters_found', 0)} clusters found")
                    else:
                        report_lines.append(f"    {key}: analysis completed")
                elif key == 'content_stats':
                    stats = after[key]
                    report_lines.append(f"    {key}: {stats.get('word_count', 0)} words, {stats.get('character_count', 0)} chars")
                elif key == 'segmentation':
                    seg = after[key]
                    report_lines.append(f"    {key}: {seg.get('total_segments', 1)} segments")
                else:
                    report_lines.append(f"    {key}: added")
    
    def _add_semantic_deduplication_details(self, report_lines: List[str], result: Dict[str, Any]) -> None:
        """Add detailed semantic deduplication examples showing clusters"""
        
        # Get original conversation lines for BEFORE
        original_lifelog = result['before_metadata'].get('original_lifelog', {})
        original_contents = original_lifelog.get('contents', [])
        
        report_lines.append("BEFORE (Original conversation with duplicates):")
        for i, node in enumerate(original_contents[:10], 1):  # Show first 10 for space
            content = node.get('content', '').strip()
            speaker = node.get('speakerName', 'Unknown')
            if node.get('speakerIdentifier') == 'user':
                speaker = f"{speaker} (You)"
            report_lines.append(f"  {i:2d}. {speaker}: {content}")
        if len(original_contents) > 10:
            report_lines.append(f"     ... and {len(original_contents) - 10} more lines")
        report_lines.append("")
        
        # Get semantic clusters for AFTER
        semantic_clusters = result['after_metadata'].get('semantic_clusters', {})
        display_conversation = result['after_metadata'].get('display_conversation', [])
        
        report_lines.append("AFTER (Deduplicated conversation with canonical lines):")
        canonical_count = 0
        for i, node in enumerate(display_conversation, 1):
            content = node.get('content', '').strip()
            speaker = node.get('speakerName', 'Unknown')
            if node.get('speakerIdentifier') == 'user':
                speaker = f"{speaker} (You)"
            
            if node.get('is_deduplicated'):
                canonical_count += 1
                hidden_count = node.get('hidden_variations', 0)
                report_lines.append(f"  {canonical_count:2d}. {speaker}: {content}")
                report_lines.append(f"       *(represents {hidden_count + 1} similar statements)*")
            elif node.get('is_unique'):
                report_lines.append(f"  U{i:2d}. {speaker}: {content} [unique]")
        report_lines.append("")
        
        # Show detailed cluster analysis
        if semantic_clusters:
            report_lines.append("SEMANTIC CLUSTERS IDENTIFIED:")
            for cluster_id, cluster_data in semantic_clusters.items():
                theme = cluster_data.get('theme', 'unknown')
                canonical = cluster_data.get('canonical', '')
                variations = cluster_data.get('variations', [])
                frequency = cluster_data.get('frequency', 0)
                
                report_lines.append(f"")
                report_lines.append(f"  Cluster: {theme} (Theme)")
                report_lines.append(f"  Canonical: \"{canonical}\"")
                report_lines.append(f"  Frequency: {frequency} similar statements")
                
                if variations:
                    report_lines.append(f"  Variations grouped together:")
                    for var in variations:
                        var_speaker = var.get('speaker', 'Unknown')
                        var_text = var.get('text', '')
                        similarity = var.get('similarity', 0.0)
                        report_lines.append(f"    - {var_speaker}: \"{var_text}\" (similarity: {similarity:.2f})")
            report_lines.append("")

async def main():
    """Main execution function"""
    
    print("Initializing Data Cleaning Pipeline Demonstration...")
    print("")
    
    # Create demo instance
    demo = DataCleaningDemo()
    
    # Generate test data
    print("Generating realistic test data with duplicates and conversation patterns...")
    test_lifelog = demo.generate_test_data()
    print(f"✓ Created test conversation with {len(test_lifelog['contents'])} spoken lines")
    print("")
    
    # Run pipeline
    print("Running complete cleaning pipeline...")
    pipeline_results = await demo.run_cleaning_pipeline()
    print(f"✓ Completed {len(pipeline_results)} processing steps")
    print("")
    
    # Generate and display report
    print("Generating detailed BEFORE/AFTER report...")
    report = demo.generate_report()
    print(report)

if __name__ == "__main__":
    asyncio.run(main())