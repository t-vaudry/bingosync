"""
Test package initialization.

Sets up environment variables before any test modules import the app.
"""

import os

# Set test environment variables before any imports
os.environ['INTERNAL_API_SECRET'] = 'test-secret-for-testing-purposes-only-32-chars'
os.environ['DEBUG'] = '1'
os.environ['DOMAIN'] = 'example.com'
