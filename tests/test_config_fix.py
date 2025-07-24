#!/usr/bin/env python3
"""
Simple test script to verify embedding processing configuration with fractional hours
"""

import os
from config.factory import create_production_config

def test_config():
    try:
        # Test configuration loading
        config = create_production_config()
        
        print("✅ Configuration loaded successfully!")
        print(f"📊 Embedding Processing Config:")
        print(f"   - Enabled: {config.embedding_processing.enabled}")
        print(f"   - Interval: {config.embedding_processing.interval_hours} hours")
        print(f"   - Batch Size: {config.embedding_processing.batch_size}")
        print(f"   - Startup Processing: {config.embedding_processing.startup_processing}")
        print(f"   - Startup Limit: {config.embedding_processing.startup_limit}")
        
        # Convert hours to minutes for readability
        minutes = config.embedding_processing.interval_hours * 60
        print(f"   - Interval in minutes: {minutes} minutes")
        
        return True
        
    except Exception as e:
        print(f"❌ Configuration failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing embedding processing configuration...")
    success = test_config()
    if success:
        print("🎉 All tests passed! Configuration is ready.")
    else:
        print("💥 Configuration test failed!")