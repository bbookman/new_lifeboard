# Essential Development Commands

## Project Setup
```bash
# Auto install (recommended)
chmod +x install_project.sh
./install_project.sh

# Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

## Development Servers
```bash
# Full stack (both backend + frontend)
./start_full_stack.sh

# Individual servers
python -m uvicorn api.server:app --reload --port 8000  # Backend
cd frontend && npm run dev                              # Frontend

# Package.json shortcuts
npm run dev:full      # Full stack
npm run dev:backend   # Backend only
npm run dev:frontend  # Frontend only
```

## Testing
```bash
# Python tests (pytest)
PYTHONPATH=. python3 -m pytest                    # All tests
PYTHONPATH=. python3 -m pytest tests/             # Specific directory
PYTHONPATH=. python3 -m pytest -v                 # Verbose
python3 -m pytest -f                              # Watch mode

# Frontend tests (vitest)
cd frontend
npm run test      # Interactive mode
npm run test:run  # CI mode
npm run test:ui   # UI mode
```

## Code Quality
```bash
# Frontend linting
cd frontend && npm run lint

# Python - no explicit linting configured, relies on IDE/editor
```

## Build & Deployment
```bash
npm run build              # Build frontend only
cd frontend && npm run build

npm run preview           # Preview built frontend
```

## Utilities & System Commands (macOS/Darwin)
```bash
# Process management
lsof -i:8000             # Check port 8000 usage
lsof -i:5173             # Check port 5173 usage
pkill -f "python.*server.py"  # Kill Python servers
pkill -f "vite"          # Kill Vite servers

# Git workflow
git status               # Check repository status
git branch              # List branches  
git add .               # Stage changes
git commit -m "message" # Commit changes

# Project navigation
find . -name "*.py" -type f    # Find Python files
grep -r "pattern" .            # Search in files
ls -la                         # List files with details
```

## Configuration
```bash
# Environment setup
cp .env.example .env     # Copy environment template
# Edit .env with your API keys and settings
```

## Log Management
```bash
# View logs (created by start_full_stack.sh)
tail -f logs/backend.log    # Backend logs
tail -f logs/frontend.log   # Frontend logs
tail -f logs/pip_install.log # Installation logs

# Clean logs
./start_full_stack.sh --delete-logs
```