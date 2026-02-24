# Bingosync Tornado Tests

## Running Tests

### Prerequisites

Install dependencies using uv (recommended) or pip:

```bash
# Using uv (from project root)
uv sync

# Or using pip
pip install -e .
```

### Run All Tests

```bash
# From bingosync-websocket directory
python -m unittest discover tests

# Or run specific test module
python -m unittest tests.test_internal_api_auth

# Or run the test file directly
python tests/test_internal_api_auth.py
```

### Run Tests with Tornado's Test Runner

```bash
python -m tornado.testing tests.test_internal_api_auth
```

## Test Structure

- `test_internal_api_auth.py` - Tests for Tornado internal API authentication
- More test files will be added as features are implemented

## Environment Variables

Tests set `INTERNAL_API_SECRET` and `DEBUG` environment variables before importing the app module.
This ensures the Tornado server starts with test-appropriate configuration.
