# Task Completion Workflow

## When Task is Completed

### 1. Code Quality Checks
```bash
# Frontend linting (required)
cd frontend && npm run lint

# Note: No explicit Python linting configured - relies on IDE/editor
```

### 2. Testing Requirements
```bash
# Run Python tests with proper path
PYTHONPATH=. python3 -m pytest

# Run frontend tests  
cd frontend && npm run test:run
```

### 3. Build Verification
```bash
# Verify frontend builds successfully
npm run build

# Test the built frontend
npm run preview
```

### 4. Development Server Testing
```bash
# Test full stack startup
./start_full_stack.sh

# Verify both servers start:
# - Backend: http://localhost:8000
# - Frontend: http://localhost:5173
```

### 5. Documentation Updates
- Update supporting_documents/Development log.md as changelog
- Group related changes under existing entries
- No need for backups - reword/reorganize as needed
- Document significant changes and decisions

### 6. Commit Guidelines
- Use descriptive commit messages
- Document cleanup and refactor actions
- Flag any deferred tasks in Development log, not as TODOs in code

### 7. Configuration Validation
- Ensure all new config added to Pydantic models
- Test with missing config to verify fail-fast behavior
- Update .env.example if new environment variables added

## Critical Rules
- **Never leave TODOs**: Complete implementations or log in Development log
- **Test First**: Auto-generate tests for new/refactored code  
- **No Bare Excepts**: Use specific exception handling
- **Python3 Only**: Never use `python` command, always `python3`
- **Desktop Focus**: Never design for mobile, desktop/laptop only

## Quality Gates
1. **Syntax**: Code compiles/parses without errors
2. **Type**: Type hints present and valid
3. **Tests**: All tests passing
4. **Build**: Frontend builds successfully  
5. **Integration**: Full stack starts without errors
6. **Documentation**: Changes documented in Development log

## Port Conflict Management
The start_full_stack.sh script aggressively manages port conflicts:
- Automatically kills processes using ports 8000 and 5173
- Uses lsof and pkill to clean up stuck processes
- Verifies ports are available before starting servers