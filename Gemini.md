This file provides instructions for Gemini on how to interact with the Lifeboard project.

## About the Project

Lifeboard is a personal dashboard application that pulls together information from various sources to give you a complete picture of your day. It's a Python-based application using the FastAPI framework.

## User Interfaces

The project currently features two distinct user interfaces:

*   **React Frontend**: Located in the `frontend/` directory, this is a modern single-page application built with React and Vite.
*   **Static HTML Frontend**: Located in the `static/` directory, this is a simpler, traditional HTML, CSS, and JavaScript interface.

## How to Run the Application

To run the main Lifeboard application (which serves both UIs), you have a few options:

*   **Backend API Only**: To start only the FastAPI server, use the following command:

    ```bash
    python -m uvicorn api.server:app --reload
    ```

*   **Full Stack (Backend + React Frontend)**: To start both the FastAPI backend and the React development server, use the provided script:

    ```bash
    ./start_full_stack.sh
    ```

    This script will automatically handle starting both services and managing their processes.

## How to Run Tests

The project uses pytest for testing. To run the test suite, use the following command:

```bash
pytest
```

## Creating tests
Every test must be written to /tests directory. Do not violate. The directory currently exists and you must not create the directory nor remove it

## Setup

To get started with the project, you can use the `setup_venv.sh` script to create and configure your Python virtual environment with all necessary dependencies:

```bash
./setup_venv.sh
```

## Key Files

- `api/server.py`: The main FastAPI application file.
- `requirements.txt`: A list of all the Python dependencies for this project.
- `tests/`: This directory contains all the tests for the project.
- `sources/`: This directory contains the different data sources that Lifeboard uses.
- `services/`: This directory contains the services that process the data from the sources.
- `core/`: This directory contains the core application logic, including database models and migrations.
- `config/`: This directory contains the configuration for the application.
- `frontend/`: Contains the React-based single-page application.
- `static/`: Contains the static HTML, CSS, and JavaScript files for the simpler frontend.
- `tools/cli_network_diagnostics.py`: A standalone command-line tool for performing network diagnostics on the Lifeboard application.