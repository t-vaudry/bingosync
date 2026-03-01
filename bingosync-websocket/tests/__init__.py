"""
Test package initialization.

Sets up environment variables before any test modules import the app.
"""

import os

# Set test environment variables before any imports (only if not already set)
os.environ.setdefault('INTERNAL_API_SECRET', 'test-secret-for-testing-purposes-only-32-chars')
os.environ.setdefault('DEBUG', '1')
os.environ.setdefault('DOMAIN', 'example.com')
