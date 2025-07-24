#!/usr/bin/env python3
"""Script to remove test files"""
import os

# Files to remove
files_to_remove = [
    "/Users/brucebookman/code/new_lifeboard/test_dimension_handling.py",
    "/Users/brucebookman/code/new_lifeboard/test_config_fix.py"
]

for file_path in files_to_remove:
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Removed: {file_path}")
    else:
        print(f"File not found: {file_path}")

print("File removal complete")