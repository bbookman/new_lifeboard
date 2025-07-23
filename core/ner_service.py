"""
Named Entity Recognition Service using spaCy

Provides industry-standard NER capabilities with relationship detection
and entity extraction for the Lifeboard application.
"""

import logging
import re
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
import spacy
from spacy.tokens import Doc, Token, Span
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Represents a detected named entity"""
    text: str
    label: str
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class Relationship:
    """Represents a relationship between entities"""
    subject: Entity
    predicate: str
    object: Entity
    confidence: float = 1.0


@dataclass
class NERResult:
    """Complete NER analysis result"""
    entities: List[Entity]
    relationships: List[Relationship]
    person_names: Set[str]
    pet_names: Set[str]
    locations: Set[str]
    organizations: Set[str]


class NERService:
    """Named Entity Recognition service using spaCy"""
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        self.model_name = model_name
        self.nlp = None
        self._pet_indicators = {
            'dog', 'dogs', 'puppy', 'puppies', 'canine', 'pup', 'pups',
            'cat', 'cats', 'kitten', 'kittens', 'feline',
            'pet', 'pets', 'animal', 'animals',
            'bird', 'birds', 'fish', 'hamster', 'rabbit'
        }
        self._ownership_patterns = {
            'my', 'his', 'her', 'their', 'our',
            'owns', 'has', 'have', 'got'
        }
        
    async def initialize(self):
        """Initialize the spaCy model"""
        try:
            logger.info(f"Loading spaCy model: {self.model_name}")
            self.nlp = spacy.load(self.model_name)
            logger.info("NER service initialized successfully")
        except OSError as e:
            logger.error(f"Failed to load spaCy model '{self.model_name}': {e}")
            logger.info("Please install the model with: python -m spacy download en_core_web_sm")
            raise
        except Exception as e:
            logger.error(f"Error initializing NER service: {e}")
            raise
    
    def extract_entities(self, text: str) -> NERResult:
        """Extract entities and relationships from text"""
        if not self.nlp:
            raise RuntimeError("NER service not initialized")
        
        doc = self.nlp(text)
        
        # First, identify potential pet names to override spaCy classifications
        potential_pets = set()
        for token in doc:
            if token.pos_ == 'PROPN' and self._is_likely_pet_name(token, doc):
                potential_pets.add(token.text)
        
        # Extract standard spaCy entities, but override pet names
        entities = []
        for ent in doc.ents:
            if ent.text.strip() in potential_pets:
                # Override with PET label
                entities.append(Entity(
                    text=ent.text.strip(),
                    label='PET',
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=0.9  # High confidence for context-based detection
                ))
            else:
                entities.append(Entity(
                    text=ent.text.strip(),
                    label=ent.label_,
                    start=ent.start_char,
                    end=ent.end_char,
                    confidence=1.0  # spaCy doesn't provide confidence scores by default
                ))
        
        # Extract custom entities (pets not already captured by spaCy)
        custom_entities = self._extract_custom_entities(doc)
        
        # Filter out duplicates based on text and position
        existing_entity_texts = {(e.text, e.start, e.end) for e in entities}
        for custom_entity in custom_entities:
            if (custom_entity.text, custom_entity.start, custom_entity.end) not in existing_entity_texts:
                entities.append(custom_entity)
        
        # Extract relationships
        relationships = self._extract_relationships(doc, entities)
        
        # Categorize entities
        person_names = {e.text for e in entities if e.label == 'PERSON'}
        pet_names = {e.text for e in entities if e.label == 'PET'}
        locations = {e.text for e in entities if e.label in ['GPE', 'LOC']}
        organizations = {e.text for e in entities if e.label in ['ORG']}
        
        return NERResult(
            entities=entities,
            relationships=relationships,
            person_names=person_names,
            pet_names=pet_names,
            locations=locations,
            organizations=organizations
        )
    
    def _extract_custom_entities(self, doc: Doc) -> List[Entity]:
        """Extract custom entities like pet names"""
        entities = []
        
        # Find potential pet names through dependency parsing and context
        for token in doc:
            if token.pos_ == 'PROPN' and not token.ent_type_:  # Proper noun not already tagged
                # Check if this proper noun is related to pet indicators
                if self._is_likely_pet_name(token, doc):
                    entities.append(Entity(
                        text=token.text,
                        label='PET',
                        start=token.idx,
                        end=token.idx + len(token.text),
                        confidence=0.8
                    ))
        
        return entities
    
    def _is_likely_pet_name(self, token: Token, doc: Doc) -> bool:
        """Determine if a proper noun is likely a pet name based on context"""
        # Skip if this looks like a human name in human context
        if token.ent_type_ == 'PERSON':
            return False
            
        # Check surrounding context for pet indicators
        window = 7  # Check 7 tokens before and after (increased)
        start = max(0, token.i - window)
        end = min(len(doc), token.i + window + 1)
        
        context_tokens = [doc[i].lemma_.lower() for i in range(start, end)]
        context_text = ' '.join([doc[i].text.lower() for i in range(start, end)])
        
        # Check for human indicators that would disqualify as pet name
        human_indicators = ['person', 'people', 'man', 'woman', 'guy', 'girl', 'boy', 'friend', 'colleague']
        if any(human_word in context_tokens for human_word in human_indicators):
            return False
        
        # Check if any pet indicators are in the context
        if any(pet_word in context_tokens for pet_word in self._pet_indicators):
            return True
        
        # Enhanced pattern matching for common pet name constructions
        pet_name_patterns = [
            r'\b' + re.escape(token.text.lower()) + r'\s+(?:is|was)\s+(?:a|an|the)\s+(?:dog|puppy|pet|cat|kitten)',
            r'(?:dog|pet|puppy|cat|kitten)\s+(?:named|called)\s+' + re.escape(token.text.lower()),
            r'(?:has|have|owns?)\s+(?:a|an)\s+(?:dog|pet|puppy|cat|kitten)\s+(?:named|called)\s+' + re.escape(token.text.lower()),
            r'(?:my|his|her|their|our)\s+(?:dog|pet|puppy|cat|kitten)\s+' + re.escape(token.text.lower()),
        ]
        
        for pattern in pet_name_patterns:
            if re.search(pattern, context_text):
                return True
        
        # Check for possessive relationships with pet words
        # Look for patterns like "Bruce's dog Grape" or "my pet Grape"
        for i in range(start, end):
            if i == token.i:
                continue
            ctx_token = doc[i]
            
            # Check for possessive + pet pattern
            if (ctx_token.lemma_.lower() in self._pet_indicators and
                abs(i - token.i) <= 4):  # Within 4 tokens (increased)
                
                # Look for possessive markers between them
                between_start = min(i, token.i)
                between_end = max(i, token.i)
                between_tokens = doc[between_start:between_end + 1]
                
                for bt in between_tokens:
                    if bt.dep_ == 'poss' or bt.text.lower() in self._ownership_patterns:
                        return True
                    # Also check for 's pattern
                    if "'s" in bt.text.lower() or "has" in bt.text.lower():
                        return True
        
        return False
    
    def _extract_relationships(self, doc: Doc, entities: List[Entity]) -> List[Relationship]:
        """Extract relationships between entities using dependency parsing"""
        relationships = []
        
        # Create entity lookup by position
        entity_by_token = {}
        for entity in entities:
            for token in doc:
                if token.idx >= entity.start and token.idx < entity.end:
                    entity_by_token[token.i] = entity
        
        # Find ownership relationships
        for token in doc:
            if token.dep_ == 'poss':  # Possessive dependency
                # Owner is the token, owned is the head
                owner_entity = entity_by_token.get(token.i)
                owned_token = token.head
                
                # Check if the owned item is a pet
                if (owner_entity and owner_entity.label == 'PERSON' and
                    owned_token.lemma_.lower() in self._pet_indicators):
                    
                    # Look for the pet's name nearby
                    pet_entity = self._find_pet_name_near_token(owned_token, entity_by_token, doc)
                    if pet_entity:
                        relationships.append(Relationship(
                            subject=owner_entity,
                            predicate='owns_pet',
                            object=pet_entity,
                            confidence=0.9
                        ))
        
        # Find verb-based relationships (has, owns, etc.)
        for token in doc:
            if token.lemma_.lower() in ['have', 'own', 'get'] and token.pos_ == 'VERB':
                subject_entity = self._find_subject_entity(token, entity_by_token)
                
                # Look for pet names in the vicinity even if not detected as entities
                if subject_entity and subject_entity.label == 'PERSON':
                    # Check for pet names within 5 tokens after the verb
                    for i in range(token.i + 1, min(len(doc), token.i + 6)):
                        potential_pet = doc[i]
                        if (potential_pet.pos_ == 'PROPN' and 
                            self._is_likely_pet_name(potential_pet, doc)):
                            
                            # Create pet entity if not already detected
                            pet_entity = Entity(
                                text=potential_pet.text,
                                label='PET',
                                start=potential_pet.idx,
                                end=potential_pet.idx + len(potential_pet.text),
                                confidence=0.8
                            )
                            
                            relationships.append(Relationship(
                                subject=subject_entity,
                                predicate='owns_pet',
                                object=pet_entity,
                                confidence=0.8
                            ))
                            break
                
                # Original logic for already detected entities
                object_entity = self._find_object_entity(token, entity_by_token)
                if (subject_entity and object_entity and
                    subject_entity.label == 'PERSON' and object_entity.label == 'PET'):
                    relationships.append(Relationship(
                        subject=subject_entity,
                        predicate='owns_pet',
                        object=object_entity,
                        confidence=0.9
                    ))
        
        return relationships
    
    def _find_pet_name_near_token(self, token: Token, entity_by_token: Dict[int, Entity], 
                                  doc: Doc, window: int = 3) -> Optional[Entity]:
        """Find a pet name entity near a given token"""
        start = max(0, token.i - window)
        end = min(len(doc), token.i + window + 1)
        
        for i in range(start, end):
            entity = entity_by_token.get(i)
            if entity and entity.label == 'PET':
                return entity
        return None
    
    def _find_subject_entity(self, verb_token: Token, entity_by_token: Dict[int, Entity]) -> Optional[Entity]:
        """Find the subject entity for a verb"""
        for child in verb_token.children:
            if child.dep_ in ['nsubj', 'nsubjpass']:
                return entity_by_token.get(child.i)
        return None
    
    def _find_object_entity(self, verb_token: Token, entity_by_token: Dict[int, Entity]) -> Optional[Entity]:
        """Find the object entity for a verb"""
        for child in verb_token.children:
            if child.dep_ in ['dobj', 'pobj']:
                # Check if this token or nearby tokens are entities
                entity = entity_by_token.get(child.i)
                if entity:
                    return entity
                
                # Check compound nouns
                for grandchild in child.children:
                    if grandchild.dep_ == 'compound':
                        entity = entity_by_token.get(grandchild.i)
                        if entity:
                            return entity
        return None
    
    def analyze_content_for_context(self, content: str) -> Dict[str, Any]:
        """Analyze content and return structured context for chat system"""
        if not content or not content.strip():
            return {}
        
        try:
            result = self.extract_entities(content)
            
            # Build structured analysis
            analysis = {
                'entities_found': set(),
                'entity_attributes': defaultdict(lambda: {'mentions': [], 'contexts': [], 'attributes': []}),
                'relationships': [],
                'behavioral_indicators': [],
                'entity_insights': []
            }
            
            # Process entities
            for entity in result.entities:
                if entity.label == 'PERSON':
                    analysis['entities_found'].add('person_mentioned')
                    key = entity.text.lower().replace(' ', '_')
                    analysis['entity_attributes'][key]['mentions'].append(entity.text)
                    analysis['entity_attributes'][key]['attributes'].append(f'type: {entity.label}')
                
                elif entity.label == 'PET':
                    analysis['entities_found'].add('pets_mentioned')
                    analysis['entities_found'].add(f'pet_name_{entity.text.lower()}')
                    pet_key = f'pet_name_{entity.text.lower()}'
                    analysis['entity_attributes'][pet_key]['mentions'].append(entity.text)
                    analysis['entity_attributes'][pet_key]['attributes'].append('type: pet')
                
                elif entity.label in ['GPE', 'LOC']:
                    analysis['entities_found'].add('location_mentioned')
                    analysis['behavioral_indicators'].append(f'location_reference: {entity.text}')
                
                elif entity.label == 'ORG':
                    analysis['entities_found'].add('organization_mentioned')
                    analysis['behavioral_indicators'].append(f'organization_reference: {entity.text}')
            
            # Process relationships
            for rel in result.relationships:
                if rel.predicate == 'owns_pet':
                    analysis['relationships'].append({
                        'type': 'pet_ownership',
                        'owner': rel.subject.text,
                        'pet': rel.object.text,
                        'confidence': rel.confidence
                    })
                    analysis['entity_insights'].append(
                        f"• PET OWNERSHIP: {rel.subject.text} owns {rel.object.text} (confidence: {rel.confidence:.2f})"
                    )
            
            # Add summary insights
            if result.person_names:
                analysis['entity_insights'].append(f"• PEOPLE: {', '.join(result.person_names)}")
            if result.pet_names:
                analysis['entity_insights'].append(f"• PETS: {', '.join(result.pet_names)}")
            if result.locations:
                analysis['entity_insights'].append(f"• LOCATIONS: {', '.join(result.locations)}")
            
            return dict(analysis)
            
        except Exception as e:
            logger.warning(f"Error in NER analysis: {e}")
            return {}
    
    def is_available(self) -> bool:
        """Check if the NER service is available"""
        return self.nlp is not None