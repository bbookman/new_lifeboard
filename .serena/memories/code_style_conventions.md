# Code Style & Conventions

## Python (Backend)
- **Python Version**: 3.9+ required, use `python3` command explicitly (never `python`)
- **Type Hints**: Always include type hints for all functions and classes
- **Naming**: snake_case for variables, functions, files; PascalCase for classes
- **Async/Await**: Use modern async patterns where appropriate
- **Configuration**: Pydantic models for all config (config/models.py), loaded via factory pattern
- **Dependency Injection**: Services designed for injection, improving testability
- **Single Responsibility**: Each service/module has clear, focused purpose

## Code Architecture Patterns
- **ABC Base Classes**: Use ABC for interfaces (e.g., BaseSource for data sources)
- **DataItem Flow**: All sources → DataItem objects → unified pipeline → data_items table
- **Namespaced IDs**: Format `namespace:source_id` for data isolation
- **Database-First Settings**: Store app settings in database, not env vars for state
- **Processor Pattern**: Use processor classes for specialized data handling

## Documentation Standards
- **Docstrings**: All functions and classes must have docstrings
- **Comments**: Explain complex logic and business rules
- **Type Annotations**: Required for all function parameters and returns

## React/TypeScript (Frontend)
- **TypeScript**: Strict typing enabled, all components typed
- **Component Library**: shadcn/ui + Radix UI components
- **Styling**: Tailwind CSS with design system approach
- **State Management**: React Query for server state, React hooks for local state
- **File Structure**: Feature-based organization in frontend/src
- **Naming**: PascalCase for components, camelCase for functions/variables

## Testing Patterns
- **Python**: pytest framework with async support, fixtures in conftest.py
- **Test Location**: All tests in /tests directory (never alongside source)  
- **Test Naming**: Prefix with `test_`, descriptive names
- **Coverage**: Aim for unit tests, integration tests, async tests as marked
- **Frontend**: vitest + Testing Library, component and integration testing

## Configuration Management
- **Environment Variables**: Use .env for local development only
- **Validation**: Pydantic models validate all config at startup
- **Fail Fast**: Application fails at startup if required config missing
- **Factory Pattern**: config/factory.py provides centralized config loading

## Error Handling
- **Specific Exceptions**: Use specific exception types, avoid bare except
- **Logging**: All errors logged to /logs directory with context
- **Graceful Degradation**: Services handle failures appropriately
- **Validation**: Input validation at API boundaries

## Import Organization
- **Standard library first**: System imports
- **Third-party second**: External package imports  
- **Local imports last**: Project-specific imports
- **Relative imports**: For same-package imports when appropriate