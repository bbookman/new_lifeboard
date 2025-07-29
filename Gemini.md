This file provides instructions for Gemini on how to interact with the Lifeboard project.

## About the Project

Lifeboard is a personal dashboard application that pulls together information from various sources to give you a complete picture of your day. It's a Python-based application using the FastAPI framework.

## How to Run the Application

To run the main Lifeboard application, use the following command:

```bash
python -m uvicorn api.server:app --reload
```

This will start the FastAPI server.

## How to Run Tests

The project uses pytest for testing. To run the test suite, use the following command:

```bash
pytest
```

## Key Files

- `api/server.py`: The main FastAPI application file.
- `requirements.txt`: A list of all the Python dependencies for this project.
- `tests/`: This directory contains all the tests for the project.
- `sources/`: This directory contains the different data sources that Lifeboard uses.
- `services/`: This directory contains the services that process the data from the sources.
- `core/`: This directory contains the core application logic, including database models and migrations.
- `config/`: This directory contains the configuration for the application.