#!/usr/bin/env python3
"""Test script to verify the config fix."""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from config.factory import create_production_config
    print("✅ Config import successful")
    
    config = create_production_config()
    print("✅ Config creation successful")
    
    # Test that auto_sync was properly removed (as per development log)
    if hasattr(config, 'auto_sync'):
        print("❌ ERROR: auto_sync field still exists in AppConfig!")
        sys.exit(1)
    else:
        print("✅ auto_sync field properly removed from AppConfig")
    
    # Test the TwitterConfig
    twitter_config = config.twitter
    print(f"✅ Twitter config: enabled={twitter_config.enabled}, data_path={twitter_config.data_path}, delete_after_import={twitter_config.delete_after_import}")
    
    # Check that the new attributes exist
    if not hasattr(twitter_config, 'data_path'):
        print("❌ ERROR: data_path missing from TwitterConfig!")
        sys.exit(1)
    if not hasattr(twitter_config, 'delete_after_import'):
        print("❌ ERROR: delete_after_import missing from TwitterConfig!")
        sys.exit(1)
    print("✅ TwitterConfig has all required attributes")
    
    print("\n🎉 All configuration tests passed!")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)