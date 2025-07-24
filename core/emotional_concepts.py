"""
Emotional Concept Engine using ConceptNet5 and curated domain knowledge
for sophisticated emotional and psychological concept expansion.
"""

import logging
import requests
import time
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import quote
import json

logger = logging.getLogger(__name__)


@dataclass
class ConceptRelation:
    """Represents a conceptual relationship"""
    concept: str
    relation_type: str
    weight: float
    source: str  # 'conceptnet', 'ontology', 'spacy'


class ConceptNet5Client:
    """Client for accessing ConceptNet5 API"""
    
    def __init__(self, base_url: str = "http://api.conceptnet.io"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Lifeboard-EmotionalConcepts/1.0'
        })
        self.cache = {}  # Simple in-memory cache
        
    def get_related_concepts(self, concept: str, limit: int = 20, 
                           min_weight: float = 1.0) -> List[ConceptRelation]:
        """Get related concepts from ConceptNet5"""
        try:
            # Check cache first
            cache_key = f"{concept}_{limit}_{min_weight}"
            if cache_key in self.cache:
                logger.debug(f"ConceptNet5: Using cached results for '{concept}'")
                return self.cache[cache_key]
            
            # Query ConceptNet5 API
            encoded_concept = quote(f"/c/en/{concept.lower().replace(' ', '_')}")
            url = f"{self.base_url}/query?node={encoded_concept}&limit={limit}"
            
            logger.debug(f"ConceptNet5: Querying {url}")
            response = self.session.get(url, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            relations = []
            
            for edge in data.get('edges', []):
                try:
                    # Extract related concept
                    start_concept = self._extract_concept(edge.get('start', {}).get('label', ''))
                    end_concept = self._extract_concept(edge.get('end', {}).get('label', ''))
                    relation = edge.get('rel', {}).get('label', '')
                    weight = edge.get('weight', 0.0)
                    
                    # Determine which concept is the related one
                    if start_concept.lower() == concept.lower():
                        related_concept = end_concept
                    elif end_concept.lower() == concept.lower():
                        related_concept = start_concept
                    else:
                        continue  # Neither matches our query concept
                    
                    # Filter by weight and validity
                    if (weight >= min_weight and 
                        related_concept and 
                        related_concept.lower() != concept.lower() and
                        len(related_concept) > 1):
                        
                        relations.append(ConceptRelation(
                            concept=related_concept.lower(),
                            relation_type=relation,
                            weight=weight,
                            source='conceptnet'
                        ))
                        
                except Exception as e:
                    logger.debug(f"ConceptNet5: Error processing edge: {e}")
                    continue
            
            # Sort by weight and remove duplicates
            unique_relations = {}
            for rel in relations:
                if rel.concept not in unique_relations or rel.weight > unique_relations[rel.concept].weight:
                    unique_relations[rel.concept] = rel
            
            final_relations = list(unique_relations.values())
            final_relations.sort(key=lambda x: x.weight, reverse=True)
            
            # Cache results
            self.cache[cache_key] = final_relations
            
            logger.info(f"ConceptNet5: Found {len(final_relations)} related concepts for '{concept}'")
            return final_relations
            
        except requests.RequestException as e:
            logger.warning(f"ConceptNet5: API request failed for '{concept}': {e}")
            return []
        except Exception as e:
            logger.error(f"ConceptNet5: Unexpected error for '{concept}': {e}")
            return []
    
    def _extract_concept(self, label: str) -> str:
        """Extract clean concept from ConceptNet label"""
        if not label:
            return ""
        
        # Remove language prefixes like '/c/en/'
        if label.startswith('/c/en/'):
            label = label[6:]
        
        # Replace underscores with spaces
        label = label.replace('_', ' ')
        
        # Clean up
        label = label.strip().lower()
        
        return label


class CuratedEmotionalOntology:
    """Curated domain knowledge for psychological and emotional concepts"""
    
    def __init__(self):
        self.emotional_clusters = {
            # Core emotions and their clinical manifestations
            'fear': {
                'primary': ['anxiety', 'worry', 'concern', 'apprehension', 'dread'],
                'clinical': ['panic', 'phobia', 'agoraphobia', 'social_anxiety'],
                'physical': ['trembling', 'sweating', 'palpitations', 'nausea'],
                'behavioral': ['avoidance', 'escape', 'freezing', 'hypervigilance']
            },
            'anxiety': {
                'primary': ['fear', 'worry', 'nervousness', 'unease', 'tension'],
                'clinical': ['generalized_anxiety', 'panic_disorder', 'ptsd'],
                'physical': ['restlessness', 'fatigue', 'muscle_tension', 'insomnia'],
                'cognitive': ['rumination', 'catastrophizing', 'racing_thoughts']
            },
            'worry': {
                'primary': ['anxiety', 'concern', 'fear', 'stress', 'unease'],
                'clinical': ['obsessive_thoughts', 'intrusive_thoughts'],
                'temporal': ['future_focus', 'what_if_thinking', 'uncertainty']
            },
            'stress': {
                'primary': ['pressure', 'strain', 'tension', 'overwhelm'],
                'physical': ['headache', 'fatigue', 'muscle_pain', 'digestive_issues'],
                'sources': ['work_stress', 'relationship_stress', 'financial_stress', 'health_stress']
            },
            'depression': {
                'primary': ['sadness', 'hopelessness', 'emptiness', 'despair'],
                'clinical': ['major_depression', 'dysthymia', 'seasonal_depression'],
                'cognitive': ['negative_thinking', 'self_criticism', 'worthlessness'],
                'behavioral': ['withdrawal', 'isolation', 'loss_of_interest']
            },
            # Health-related emotional concepts
            'health_anxiety': {
                'primary': ['medical_worry', 'illness_fear', 'symptom_focus'],
                'triggers': ['doctor_visits', 'test_results', 'physical_symptoms'],
                'behaviors': ['body_checking', 'medical_googling', 'reassurance_seeking']
            },
            # Social and relationship concepts
            'social_anxiety': {
                'primary': ['social_fear', 'performance_anxiety', 'embarrassment_fear'],
                'situations': ['public_speaking', 'social_gatherings', 'meeting_new_people'],
                'symptoms': ['blushing', 'stuttering', 'social_withdrawal']
            }
        }
        
        # Intensity modifiers for emotional concepts
        self.intensity_modifiers = {
            'high': ['extremely', 'severely', 'intensely', 'overwhelming', 'unbearable'],
            'medium': ['quite', 'fairly', 'moderately', 'considerably'],
            'low': ['slightly', 'mildly', 'somewhat', 'a_little', 'barely']
        }
        
        # Temporal patterns
        self.temporal_patterns = {
            'chronic': ['ongoing', 'persistent', 'long_term', 'constant'],
            'episodic': ['occasional', 'intermittent', 'periodic', 'recurring'],
            'acute': ['sudden', 'immediate', 'intense', 'short_term']
        }
    
    def enhance_concepts(self, base_concepts: List[str], 
                        include_clinical: bool = True,
                        include_physical: bool = True) -> List[ConceptRelation]:
        """Enhance concept list with curated domain knowledge"""
        enhanced = []
        processed = set()
        
        for concept in base_concepts:
            concept_lower = concept.lower()
            
            # Skip if already processed
            if concept_lower in processed:
                continue
            processed.add(concept_lower)
            
            # Find matches in emotional clusters
            for cluster_name, cluster_data in self.emotional_clusters.items():
                if (concept_lower == cluster_name or 
                    concept_lower in cluster_data.get('primary', [])):
                    
                    # Add primary relationships
                    for related in cluster_data.get('primary', []):
                        if related != concept_lower:
                            enhanced.append(ConceptRelation(
                                concept=related,
                                relation_type='emotional_primary',
                                weight=3.0,
                                source='ontology'
                            ))
                    
                    # Add clinical terms if requested
                    if include_clinical:
                        for related in cluster_data.get('clinical', []):
                            enhanced.append(ConceptRelation(
                                concept=related,
                                relation_type='clinical_manifestation',
                                weight=2.5,
                                source='ontology'
                            ))
                    
                    # Add physical symptoms if requested
                    if include_physical:
                        for related in cluster_data.get('physical', []):
                            enhanced.append(ConceptRelation(
                                concept=related,
                                relation_type='physical_symptom',
                                weight=2.0,
                                source='ontology'
                            ))
                    
                    # Add behavioral indicators
                    for related in cluster_data.get('behavioral', []):
                        enhanced.append(ConceptRelation(
                            concept=related,
                            relation_type='behavioral_indicator',
                            weight=2.0,
                            source='ontology'
                        ))
        
        return enhanced
    
    def get_intensity_variants(self, concept: str) -> List[ConceptRelation]:
        """Get intensity variants of emotional concepts"""
        variants = []
        
        for intensity, modifiers in self.intensity_modifiers.items():
            for modifier in modifiers:
                variants.append(ConceptRelation(
                    concept=f"{modifier} {concept}",
                    relation_type=f'intensity_{intensity}',
                    weight=2.0 if intensity == 'high' else 1.5,
                    source='ontology'
                ))
        
        return variants


class EmotionalConceptEngine:
    """
    Main engine for emotional concept expansion using ConceptNet5 + curated knowledge
    """
    
    def __init__(self, use_spacy_fallback: bool = True):
        self.conceptnet = ConceptNet5Client()
        self.ontology = CuratedEmotionalOntology()
        self.use_spacy_fallback = use_spacy_fallback
        self.spacy_nlp = None
        
        # Initialize spaCy if available
        if use_spacy_fallback:
            try:
                import spacy
                self.spacy_nlp = spacy.load("en_core_web_sm")
                logger.info("EmotionalConceptEngine: spaCy fallback enabled")
            except (ImportError, OSError) as e:
                logger.warning(f"EmotionalConceptEngine: spaCy not available: {e}")
                self.use_spacy_fallback = False
    
    def expand_emotional_concepts(self, concepts: List[str], 
                                max_expansions: int = 15,
                                similarity_threshold: float = 0.6) -> List[str]:
        """
        Expand emotional concepts using hybrid approach
        
        Args:
            concepts: List of base concepts to expand
            max_expansions: Maximum number of related concepts to return
            similarity_threshold: Minimum similarity threshold for inclusion
            
        Returns:
            List of expanded concept terms
        """
        all_relations = []
        processed_concepts = set()
        
        logger.info(f"🧠 CONCEPT EXPANSION: Expanding {len(concepts)} concepts: {concepts}")
        
        for concept in concepts:
            concept_clean = concept.lower().strip()
            if concept_clean in processed_concepts or len(concept_clean) < 2:
                continue
            processed_concepts.add(concept_clean)
            
            # 1. Get ConceptNet5 relations (primary source)
            conceptnet_relations = self.conceptnet.get_related_concepts(
                concept_clean, 
                limit=20, 
                min_weight=1.0
            )
            all_relations.extend(conceptnet_relations)
            
            # 2. Enhance with curated ontology
            ontology_relations = self.ontology.enhance_concepts([concept_clean])
            all_relations.extend(ontology_relations)
            
            # 3. Add intensity variants
            intensity_variants = self.ontology.get_intensity_variants(concept_clean)
            all_relations.extend(intensity_variants[:3])  # Limit intensity variants
        
        # 4. spaCy fallback if needed and no good results
        if (len(all_relations) < 5 and 
            self.use_spacy_fallback and 
            self.spacy_nlp):
            
            logger.info("🧠 CONCEPT EXPANSION: Using spaCy fallback for additional concepts")
            spacy_relations = self._spacy_concept_expansion(concepts, max_expansions=10)
            all_relations.extend(spacy_relations)
        
        # Process and rank all relations
        return self._process_and_rank_relations(all_relations, max_expansions, similarity_threshold)
    
    def _spacy_concept_expansion(self, concepts: List[str], max_expansions: int = 10) -> List[ConceptRelation]:
        """Use spaCy for semantic similarity expansion"""
        if not self.spacy_nlp:
            return []
        
        spacy_relations = []
        
        # Define emotional vocabulary for similarity comparison
        emotional_vocab = [
            'anxiety', 'fear', 'worry', 'stress', 'concern', 'panic', 'nervous',
            'health', 'medical', 'doctor', 'symptoms', 'illness', 'pain',
            'social', 'meeting', 'people', 'friends', 'family', 'work',
            'tired', 'exhausted', 'sleep', 'rest', 'fatigue',
            'sad', 'happy', 'angry', 'frustrated', 'overwhelmed'
        ]
        
        try:
            for concept in concepts:
                concept_doc = self.spacy_nlp(concept.lower())
                
                for vocab_word in emotional_vocab:
                    if vocab_word.lower() == concept.lower():
                        continue
                        
                    vocab_doc = self.spacy_nlp(vocab_word)
                    similarity = concept_doc.similarity(vocab_doc)
                    
                    if similarity > 0.5:  # Threshold for spaCy similarity
                        spacy_relations.append(ConceptRelation(
                            concept=vocab_word,
                            relation_type='semantic_similarity',
                            weight=similarity * 2.0,  # Scale to match ConceptNet weights
                            source='spacy'
                        ))
            
            # Sort by similarity and limit
            spacy_relations.sort(key=lambda x: x.weight, reverse=True)
            return spacy_relations[:max_expansions]
            
        except Exception as e:
            logger.warning(f"spaCy concept expansion failed: {e}")
            return []
    
    def _process_and_rank_relations(self, relations: List[ConceptRelation], 
                                  max_expansions: int,
                                  similarity_threshold: float) -> List[str]:
        """Process and rank all concept relations"""
        
        # Deduplicate and combine weights for same concepts
        concept_scores = {}
        for relation in relations:
            concept = relation.concept.lower()
            if concept in concept_scores:
                # Combine scores, giving preference to higher quality sources
                existing_weight = concept_scores[concept]['weight']
                source_bonus = {
                    'ontology': 1.5,      # Highest priority for curated knowledge
                    'conceptnet': 1.2,    # High priority for ConceptNet
                    'spacy': 1.0          # Standard priority for spaCy
                }.get(relation.source, 1.0)
                
                combined_weight = max(existing_weight, relation.weight * source_bonus)
                concept_scores[concept] = {
                    'weight': combined_weight,
                    'sources': concept_scores[concept]['sources'] + [relation.source]
                }
            else:
                source_bonus = {
                    'ontology': 1.5,
                    'conceptnet': 1.2,
                    'spacy': 1.0
                }.get(relation.source, 1.0)
                
                concept_scores[concept] = {
                    'weight': relation.weight * source_bonus,
                    'sources': [relation.source]
                }
        
        # Filter by threshold and sort
        filtered_concepts = [
            (concept, data) for concept, data in concept_scores.items()
            if data['weight'] >= similarity_threshold
        ]
        
        filtered_concepts.sort(key=lambda x: x[1]['weight'], reverse=True)
        
        # Extract final concept list
        final_concepts = [concept for concept, data in filtered_concepts[:max_expansions]]
        
        logger.info(f"🧠 CONCEPT EXPANSION: Final {len(final_concepts)} concepts: {final_concepts}")
        logger.debug(f"🧠 CONCEPT EXPANSION: Detailed scores: {[(c, d['weight'], d['sources']) for c, d in filtered_concepts[:max_expansions]]}")
        
        return final_concepts
    
    def get_concept_analysis(self, concept: str) -> Dict[str, any]:
        """Get detailed analysis of a single concept"""
        analysis = {
            'concept': concept,
            'conceptnet_relations': [],
            'ontology_relations': [],
            'spacy_similarity': [],
            'total_related': 0
        }
        
        # ConceptNet analysis
        conceptnet_relations = self.conceptnet.get_related_concepts(concept, limit=10)
        analysis['conceptnet_relations'] = [
            {'concept': r.concept, 'relation': r.relation_type, 'weight': r.weight}
            for r in conceptnet_relations
        ]
        
        # Ontology analysis
        ontology_relations = self.ontology.enhance_concepts([concept])
        analysis['ontology_relations'] = [
            {'concept': r.concept, 'relation': r.relation_type, 'weight': r.weight}
            for r in ontology_relations
        ]
        
        analysis['total_related'] = len(conceptnet_relations) + len(ontology_relations)
        
        return analysis