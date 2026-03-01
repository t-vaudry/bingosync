# Testing Guide

## Test Organization

Tests are organized in dedicated `tests/` directories:

```
bingosync-app/
  └── tests/
      ├── __init__.py
      ├── README.md
      └── test_internal_api_auth.py

bingosync-websocket/
  └── tests/
      ├── __init__.py
      ├── README.md
      └── test_internal_api_auth.py
```

## Running Tests

### Prerequisites

Install dependencies using uv (recommended):

```bash
# From project root
uv sync
```

Or using pip:

```bash
pip install -e .
```

### Django Tests (bingosync-app)

```bash
cd bingosync-app

# Run all tests
python manage.py test

# Run specific test module
python manage.py test tests.test_internal_api_auth

# Run with verbose output
python manage.py test --verbosity=2
```

### Tornado Tests (bingosync-websocket)

```bash
cd bingosync-websocket

# Run all tests (recommended - sets up environment correctly)
python run_tests.py

# Alternative: Run with unittest discover (may have environment issues)
python -m unittest discover tests -v

# Run specific test module
python -m unittest tests.test_internal_api_auth -v
```

**Note:** The `run_tests.py` script is recommended as it ensures environment variables are set correctly before importing the app module.

## Current Test Coverage

### Internal API Authentication Tests

**Django (3 tests):**
- ✅ `test_get_internal_api_headers_includes_secret` - Verifies header generation
- ✅ `test_publish_json_sends_internal_secret` - Verifies event publishing includes auth
- ✅ `test_internal_api_secret_is_configured` - Verifies settings configuration

**Tornado (5 tests):**
- ✅ `test_main_handler_requires_auth` - Verifies MainHandler authentication
- ✅ `test_connected_handler_requires_auth` - Verifies ConnectedHandler authentication
- ✅ `test_validate_internal_request_with_valid_secret` - Validates correct secret
- ✅ `test_validate_internal_request_with_invalid_secret` - Rejects wrong secret
- ✅ `test_validate_internal_request_with_missing_header` - Rejects missing header

## Test Environment

Tests automatically use test-specific configurations:

- Django: `IS_TEST` flag in settings.py triggers test mode
- Tornado: Environment variables set before app import
- Both: `INTERNAL_API_SECRET` uses test value automatically

## Adding New Tests

1. Create test file in appropriate `tests/` directory
2. Name file with `test_` prefix (e.g., `test_feature_name.py`)
3. Import appropriate test framework:
   - Django: `from django.test import TestCase`
   - Tornado: `import unittest` (use standard unittest)
4. Create test classes inheriting from test case
5. Add test methods with `test_` prefix
6. Run the tests to verify they work

## Continuous Integration

Tests should be run in CI/CD pipeline:

```yaml
# Example GitHub Actions workflow
- name: Run Django Tests
  run: |
    cd bingosync-app
    python manage.py test

- name: Run Tornado Tests
  run: |
    cd bingosync-websocket
    python -m unittest discover tests
```

## Future Test Additions

As per the spec (Task 4.6-4.9), additional tests will be added for:

- Models (User, Room, Game, Player, Square, Events, Achievements)
- Forms and validators
- Views and API endpoints
- Integration tests for complete workflows
- WebSocket communication
- Role-based permissions
- Counter claim review system
- Fog of war functionality
- Achievement system

Target: 60% code coverage minimum
