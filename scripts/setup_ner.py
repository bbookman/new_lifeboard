#!/usr/bin/env python3
"""
Setup script for NER service - ensures spaCy model is available
"""

import sys
import subprocess
import asyncio

async def setup_ner():
    """Setup and test NER service"""
    print("🔧 Setting up NER service...")
    
    try:
        # Try to import spaCy
        import spacy
        print("✅ spaCy library found")
        
        # Try to load the model
        try:
            nlp = spacy.load("en_core_web_sm")
            print("✅ en_core_web_sm model loaded successfully")
        except OSError:
            print("⚠️  en_core_web_sm model not found, attempting to download...")
            
            # Download the model
            result = subprocess.run([
                sys.executable, "-m", "spacy", "download", "en_core_web_sm"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                print("✅ Model downloaded successfully")
                nlp = spacy.load("en_core_web_sm")
                print("✅ Model loaded after download")
            else:
                print(f"❌ Failed to download model: {result.stderr}")
                print("🔄 Will use fallback mode")
    
    except ImportError:
        print("❌ spaCy not installed, please install with: pip install spacy>=3.7.0")
        return False
    
    # Test the NER service
    print("\n🧪 Testing NER service...")
    
    try:
        from core.ner_service import NERService
        
        ner = NERService()
        await ner.initialize()
        
        print(f"✅ NER service initialized (spaCy available: {ner.nlp is not None})")
        
        # Test with sample text
        test_text = "Bruce has a dog named Grape. Grape is a very good dog."
        result = ner.extract_entities(test_text)
        
        print(f"🎯 Test results:")
        print(f"   Entities found: {len(result.entities)}")
        print(f"   Relationships: {len(result.relationships)}")
        print(f"   Person names: {result.person_names}")
        print(f"   Pet names: {result.pet_names}")
        
        for entity in result.entities:
            print(f"   - {entity.text} ({entity.label}, confidence: {entity.confidence:.2f})")
        
        for rel in result.relationships:
            print(f"   - {rel.subject.text} {rel.predicate} {rel.object.text} (confidence: {rel.confidence:.2f})")
        
        print("✅ NER service test completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ NER service test failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(setup_ner())
    if success:
        print("\n🎉 NER service setup completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ NER service setup failed")
        sys.exit(1)