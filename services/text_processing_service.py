"""
Text Processing Service

Centralized text processing utilities for keyword extraction, text cleaning,
and stemming/lemmatization with comprehensive logging.
"""

import re
import time
import logging
from typing import List, Set, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TextProcessingConfig:
    """Configuration for text processing operations"""
    minimum_keyword_length: int = 2
    maximum_keyword_length: int = 50
    keyword_search_mode: str = "OR"  # "AND" or "OR"
    max_keywords_per_query: int = 10
    enable_stemming: bool = True
    custom_stop_words: Optional[List[str]] = None


class TextProcessingService:
    """Service for text processing, keyword extraction, and text normalization"""
    
    # Common English stop words
    DEFAULT_STOP_WORDS = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
        'to', 'was', 'were', 'will', 'with', 'would', 'could', 'should',
        'about', 'after', 'all', 'also', 'am', 'any', 'been', 'but', 'can',
        'do', 'does', 'did', 'had', 'have', 'how', 'i', 'if', 'into', 'no',
        'not', 'or', 'so', 'some', 'than', 'then', 'there', 'these', 'they',
        'this', 'we', 'what', 'when', 'where', 'who', 'why', 'you', 'your'
    }
    
    def __init__(self, config: Optional[TextProcessingConfig] = None):
        # Import here to avoid circular imports
        if config is None:
            from config.models import TextProcessingConfig
            config = TextProcessingConfig()
        
        self.config = config
        
        # Initialize stop words
        self.stop_words = self.DEFAULT_STOP_WORDS.copy()
        if self.config.custom_stop_words:
            self.stop_words.update(word.lower() for word in self.config.custom_stop_words)
        
        # Compile regex patterns for efficiency
        self.whitespace_pattern = re.compile(r'\s+')
        self.control_chars_pattern = re.compile(r'[\x00-\x1f\x7f-\x9f]')
        self.word_pattern = re.compile(r'\b[a-zA-Z0-9]+\b')
        self.punctuation_pattern = re.compile(r'[^\w\s]')
        
        logger.info(f"TextProcessingService initialized with {len(self.stop_words)} stop words, "
                   f"stemming={'enabled' if self.config.enable_stemming else 'disabled'}")
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        start_time = time.time()
        
        # Remove control characters
        cleaned = self.control_chars_pattern.sub(' ', text)
        
        # Normalize whitespace
        cleaned = self.whitespace_pattern.sub(' ', cleaned)
        
        # Strip leading/trailing whitespace
        cleaned = cleaned.strip()
        
        duration = time.time() - start_time
        logger.debug(f"Text cleaned: {len(text)} -> {len(cleaned)} chars in {duration:.3f}s")
        
        return cleaned
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text with stemming/lemmatization"""
        if not text:
            logger.debug("Empty text provided for keyword extraction")
            return []
        
        start_time = time.time()
        logger.debug(f"Extracting keywords from text: {text[:100]}{'...' if len(text) > 100 else ''}")
        
        try:
            # Step 1: Clean the text
            cleaned_text = self.clean_text(text)
            
            # Step 2: Convert to lowercase for processing
            lower_text = cleaned_text.lower()
            
            # Step 3: Extract words using regex
            words = self.word_pattern.findall(lower_text)
            
            # Step 4: Filter words
            keywords = []
            for word in words:
                # Skip if too short or too long
                if len(word) < self.config.minimum_keyword_length or len(word) > self.config.maximum_keyword_length:
                    continue
                
                # Skip stop words
                if word in self.stop_words:
                    continue
                
                # Skip purely numeric
                if word.isdigit():
                    continue
                
                # Apply stemming if enabled
                if self.config.enable_stemming:
                    word = self._apply_stemming(word)
                
                keywords.append(word)
            
            # Step 5: Remove duplicates while preserving order
            unique_keywords = []
            seen = set()
            for keyword in keywords:
                if keyword not in seen:
                    unique_keywords.append(keyword)
                    seen.add(keyword)
            
            # Step 6: Limit number of keywords
            if len(unique_keywords) > self.config.max_keywords_per_query:
                logger.debug(f"Limiting keywords from {len(unique_keywords)} to {self.config.max_keywords_per_query}")
                unique_keywords = unique_keywords[:self.config.max_keywords_per_query]
            
            duration = time.time() - start_time
            logger.info(f"Extracted {len(unique_keywords)} keywords: {unique_keywords} in {duration:.3f}s")
            
            return unique_keywords
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Keyword extraction failed for text '{text[:50]}...': {str(e)} in {duration:.3f}s")
            return []
    
    def _apply_stemming(self, word: str) -> str:
        """Apply basic stemming rules to normalize word forms"""
        # This is a simple rule-based stemmer
        # For production, consider using nltk.stem or similar libraries
        
        if len(word) <= 3:
            return word
        
        # Remove common suffixes
        suffixes = [
            ('ing', ''),      # running -> run
            ('ed', ''),       # walked -> walk
            ('er', ''),       # bigger -> big
            ('est', ''),      # biggest -> big
            ('ly', ''),       # quickly -> quick
            ('ness', ''),     # happiness -> happi
            ('ment', ''),     # development -> develop
            ('tion', ''),     # creation -> creat
            ('sion', ''),     # decision -> decis
            ('ies', 'y'),     # cities -> city
            ('ied', 'y'),     # tried -> try
            ('ies', 'y'),     # flies -> fly
            ('s', ''),        # cats -> cat (but be careful with this)
        ]
        
        # Apply suffix removal rules
        for suffix, replacement in suffixes:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                return word[:-len(suffix)] + replacement
        
        return word
    
    def get_processing_stats(self) -> dict:
        """Get current processing configuration and stats"""
        return {
            "stop_words_count": len(self.stop_words),
            "min_keyword_length": self.config.minimum_keyword_length,
            "max_keyword_length": self.config.maximum_keyword_length,
            "max_keywords_per_query": self.config.max_keywords_per_query,
            "stemming_enabled": self.config.enable_stemming,
            "search_mode": self.config.keyword_search_mode
        }