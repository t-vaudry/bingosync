# Bingosync Django Tests

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
# From bingosync-app directory
python manage.py test

# Or run specific test module
python manage.py test tests.test_internal_api_auth
```

### Run Tests with Coverage

```bash
# Install coverage
pip install coverage

# Run with coverage
coverage run --source='.' manage.py test
coverage report
```

## Test Structure

- `test_internal_api_auth.py` - Tests for Django-Tornado shared secret authentication
- More test files will be added as features are implemented

## Environment Variables

Tests use the `IS_TEST` flag in settings.py to use test-specific configurations.
The `INTERNAL_API_SECRET` is automatically set to a test value when running tests.
