#!/usr/bin/env python3
"""
Quick script to fix API test files by removing manual patches
since we're using FastAPI dependency overrides
"""

import re
import os

test_files = [
    'tests/api/test_health_routes.py',
    'tests/api/test_chat_routes.py', 
    'tests/api/test_calendar_routes.py',
    'tests/api/test_sync_routes.py',
    'tests/api/test_system_routes.py'
]

def fix_file(filepath):
    """Fix a test file by removing manual patches"""
    print(f"Fixing {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Add dependency imports if not present
    if 'from core.dependencies import' not in content:
        imports_section = content.find('from api.routes.')
        if imports_section != -1:
            line_end = content.find('\n', imports_section)
            dependency_name = filepath.split('_')[1]  # extract route name
            import_line = f"from core.dependencies import get_startup_service_dependency\n"
            content = content[:line_end+1] + import_line + content[line_end+1:]
    
    # Fix app fixture to use dependency overrides
    app_fixture_pattern = r'@pytest\.fixture\s+def app\(self\):(.*?)return app'
    
    def replace_app_fixture(match):
        return '''@pytest.fixture
    def app(self, mock_startup_service):
        """Create FastAPI test application with mocked dependencies"""
        app = FastAPI()
        app.include_router(router)
        
        # Override the dependency with our mock
        app.dependency_overrides[get_startup_service_dependency] = lambda: mock_startup_service
        return app'''
    
    content = re.sub(app_fixture_pattern, replace_app_fixture, content, flags=re.DOTALL)
    
    # Remove manual patching lines
    lines = content.split('\n')
    fixed_lines = []
    skip_next = False
    
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
            
        if 'with patch(' in line and 'get_startup_service_dependency' in line:
            # Find the actual request line and unindent it
            for j in range(i+1, min(i+10, len(lines))):
                if 'response = client.' in lines[j]:
                    # Unindent this line and following lines until we find dedent
                    indent_removed = 0
                    original_indent = len(lines[j]) - len(lines[j].lstrip())
                    new_indent = original_indent - 8  # Remove one level of indentation
                    
                    fixed_lines.append(' ' * new_indent + lines[j].strip())
                    
                    # Look for following lines that need unindenting
                    for k in range(j+1, len(lines)):
                        next_line = lines[k]
                        if next_line.strip() == '':
                            fixed_lines.append(next_line)
                        elif len(next_line) - len(next_line.lstrip()) <= original_indent and next_line.strip():
                            # This line is back to original indentation or less - we're done
                            break
                        else:
                            # Unindent this line too
                            line_indent = len(next_line) - len(next_line.lstrip())
                            new_line_indent = max(0, line_indent - 8)
                            fixed_lines.append(' ' * new_line_indent + next_line.strip())
                    
                    # Skip all the lines we just processed
                    skip_to = k
                    for skip_i in range(i, skip_to):
                        pass
                    break
            continue
        else:
            fixed_lines.append(line)
    
    # Write fixed content
    with open(filepath, 'w') as f:
        f.write('\n'.join(fixed_lines))
    
    print(f"Fixed {filepath}")

if __name__ == '__main__':
    for test_file in test_files:
        if os.path.exists(test_file):
            fix_file(test_file)
        else:
            print(f"File not found: {test_file}")
    
    print("Done fixing test files!")