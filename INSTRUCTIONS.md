mode: code development planning
---

# Instructions for AI Coding Assistants: Trading Strategies Application

## 1. Project and Application Overview

You are an AI code assistant who is an expert Python developer.

The goal of this new application is to develop another application in this broader code base that will run trading investment strategies.

As with the other apps, this new one must be a scalable FastAPI application to serve multiple calls from an orchestrator application to be developed later on.

Before proceeding, access and read the files and folders of the broader project in order for you to understand what the project so far.

This new application will be developed under `/trading` in the root directory.

Store all your progress in our development in CLAUDE.md in the root directory througout the development of the application.

## 2. Basic Implementation Instructions

- Container: The application must be able to be executed with both a local enviroment (`.venv`) and Docker.
- Framework: Use FastAPI for its performance, type hinting (Pydantic), and automatic documentation.
- Input Handling: The API calls from API clients will send a JSON payload containing all the parameters for the code to run.
- API Endpoint: The API will have a single endpoint (e.g., `/trading/routes/endpoints.py`) `/execute` (POST) which receives the JSON payload with the parameters and returns a JSON object with the results.
- Schemas: Will should have Pydantic schemas defined in `/trading/schemas/schema.py` to validate the specific inputs and outputs for its endpoints.
- Authentication: API key authentication will be implemented using the standard Authorization HTTP header (e.g., Authorization: Bearer YOUR_KEY), validated via a dependency in `/trading/core/security.py`.

## 3. Application Structure

Here is the proposed new application structure. Use this as the basis and propose changes to this structure if you have suggestions on a better way.

sapheneia/
├── ...
├── trading/                             # Main application source code
│   ├── __init__.py
│   ├── main.py                          # FastAPI app instance and root/health endpoints
│   └── routes/                          # API endpoints/routers
│   │   ├── __init__.py
│   │   ├── endpoints.py                 # Inference endpoints logic
│   │   └── ...
│   └── schemas/                         # Pydantic models for request/response validations
│   │   ├── __init__.py
│   │   ├── base.py                      # Base schemas if there's overlap
│   │   ├── schema.py                    # Schemas for inputs and outputs validation
│   │   └── ...
│   └── tests/                           # Unit and integration tests
│   │   └──  ...
│   ├── core/                            # Core logic and configuration
│   │   ├── __init__.py
│   │   ├── config.py                    # Settings management (e.g., loading secrets)
│   │   └── security.py                  # API key validation
│   ├── sample/                          # Core logic and configuration
│   │   ├── sample-code.py               # Sample code to help the initial building of the application
│   │   └── example-usage.py             # Application usage examples
│   └── ...
└── ...

## 4. Core Trading Logic Reference

In order to assist with building the application, sample code is provided under `/trading/sample/sample-code.py` which consists of:

- **Three strategy types**: `threshold`, `return`, and `quantile`
- **Stateless execution**: All state (position, cash) comes from orchestrator via parameters
- **Long-only positions**: No short selling allowed
- **OHLC data support**: Strategies use open/high/low/close historical price data
- **Key classes**:
  - `TradingStrategy`: Main stateless class with static methods
  - Helper enums: `StrategyType`, `ThresholdType`, `PositionSizing`, `WhichHistory`

The API endpoint must accept all parameters defined in `PARAMETER_STRATEGY_MAP` and return results from `execute_trading_signal()`.

## 5. Sample Code

Sample code is provided under `/trading/sample/`:
- `sample-code.py`: Complete `TradingStrategy` class implementation with all three strategies
- `example-usage.py`: Usage examples showing how to call each strategy type
- `PARAMETER_STRATEGY_MAP`: Dictionary defining all required/optional parameters per strategy

**Important**: The API endpoint should accept the same parameter structure as shown in `example_usage.py` and wrap the `TradingStrategy.execute_trading_signal()` method.

## 6. Testing Requirements

- Unit tests for each strategy type (threshold, return, quantile)
- Integration tests for the `/execute` endpoint
- Test cases should cover:
  - Valid parameter combinations for all three strategies
  - Edge cases (insufficient cash, no position to sell, stopped strategies)
  - Invalid inputs (missing required params, wrong types)
  - Authentication failures
- Use `pytest` for testing framework

## 7. Logging

- Use Python's `logging` module for all logging
- Log levels:
  - INFO: Successful trade executions, API calls
  - WARNING: Strategies stopped, insufficient capital
  - ERROR: Invalid parameters, authentication failures
- Include request IDs for tracing in production
- Configure log format and destination in `core/config.py`

## 8. API Response Schema

The `/execute` endpoint must return:
```json
{
  "action": "buy|sell|hold",
  "size": 0.0,
  "value": 0.0,
  "reason": "string",
  "available_cash": 0.0,
  "position_after": 0.0,
  "stopped": false
}
```

Status codes:
- 200: Successful execution
- 400: Invalid parameters
- 401: Authentication failure
- 500: Internal server error

## 9. Performance Requirements

- The API must handle concurrent requests efficiently
- Strategy calculations are stateless and can be parallelized
- Use async endpoints where beneficial
- Consider rate limiting for production deployment
- Target response time: <100ms for typical requests

## 10. Required environment variables in `.env`:

- `TRADING_API_KEY`: Authentication key for the trading API
- `PYTHONPATH`: Should include project root
- `LOG_LEVEL`: Default logging level (INFO, DEBUG, WARNING, ERROR)
- `TRADING_API_HOST`: API host (default: 0.0.0.0)
- `TRADING_API_PORT`: API port (default: 8000)

## 11. Docker Configuration

- Dockerfile must be optimized for `uv` and FastAPI
- Use multi-stage builds to minimize image size
- Expose the appropriate port (default: 8000)
- Include health check endpoint
- Mount volumes for logs if needed
- The Docker image should include all dependencies from `pyproject.toml`

## 12. Security

- API keys must be validated on every request
- Never log sensitive information (API keys, trade amounts in production)
- Input validation through Pydantic schemas is mandatory
- Rate limiting should be implemented to prevent abuse
- CORS configuration should be restrictive in production

## 13. Version Control

- Follow conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, etc.
- Update `CLAUDE.md` with each significant development milestone
- Include the trading strategy version in API responses
- Tag releases semantically (v1.0.0, v1.1.0, etc.)

## 14. Setup Script (`setup.sh`), Dependency and Environment Management with `uv`

This project uses `uv` for high-performance environment creation, dependency management, virtual environments, and running Python code. Keep it minimal and always default to `uv`.

**Essential Rules**:
- Dependency file: All project metadata and dependencies must be managed in the `pyproject.toml` file. Use the `[project]` and `[project.dependencies]` sections.
- Virtual environment (`venv`): The `setup.sh` script will manage the manage the virtual environment using `uv venv`.
- Install runtime dependency: `uv add <package>`
- Install dev / test dependency: `uv add --dev <package>`
- Run a script: `uv run main.py` (or another file)
- Remove a dependency: `uv remove <package>`
- Always make sure you are executing commands inside of the virtual environment created by `uv`
- Install all project dependencies from `pyproject.toml`. This ensures the environment exactly matches the specified dependencies.
- Print a success message indicating the environment is ready.
- Use a `.env` file to store local environmental variables such as API keys, local directories, etc. This file will be added to `.gitignore`.
- The script must provide support to running the app with `.venv` and Docker.
- All enviromental variables will be defined in the `.env` file including PYTHON_PATH. Do not hard code them inside `setup.sh` and list them down in `.env`.
- The project must support `.venv` virtual enviroment as well as Docker containers. This option should be defined with `setup.sh`.

Avoid using `pip install`, `poetry add`, `conda install`, or manual venv activation unless I explicitly say uv cannot be used. If I ask for something like "install X" or "run Y": assume the `uv` form automatically without extra explanation.

## 15. Coding Standards and Conventions

Please follow these standards when writing Python code:

- **Style:** Adhere strictly to the **PEP 8** style guide. Use an autoformatter like `black` if possible.
- **Type Hinting:** All function signatures must include type hints for arguments and return values.
- **Docstrings:** All modules, classes, and functions must have clear, descriptive docstrings explaining their purpose, arguments, and return values. Use the Google Python Style Guide for docstrings.
- **Modularity:** Write small, single-responsibility functions. The core parsing logic should be encapsulated within its respective parser class.
- **Error Handling:** Use `try...except` blocks for network requests and file operations to handle potential errors gracefully. Use the `logging` module for outputting information, warnings, and errors.
- **Constants and Configuration:** Do not hardcode URLs, file paths, or lists of sources directly in the logic. All such configurations must reside in `config.py`.

## 16. `.gitignore` and `README.md`

- A standard Python `.gitignore` file that ignores `__pycache__`, `.venv`, `.env`, and IDE-specific folders.
- Edit and adjust `README.md` to explain the applications's purpose and provide clear instructions on how to use the `setup.sh` script. Include `curl` examples for testing the API, and explicit instrucation on how to run this code.

## 17. Implementation Plan

CRITICAL: Create a comprehensive planning document IMPLEMENTATIONPLAN.md in the root directory. Do not change or add any code at first, I will evaluate the implementation plan. Only proceed with code implementation once I give the go signal.