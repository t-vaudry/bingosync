#!/usr/bin/env python
"""
Test runner that ensures environment variables are set before importing app module.
"""

import os
import sys
import unittest

# Set test environment variables BEFORE any imports
os.environ['INTERNAL_API_SECRET'] = 'test-secret-for-testing-purposes-only-32-chars'
os.environ['DEBUG'] = '1'
os.environ['DOMAIN'] = 'example.com'

# Now discover and run tests
if __name__ == '__main__':
    loader = unittest.TestLoader()
    start_dir = 'tests'
    suite = loader.discover(start_dir, pattern='test_*.py')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)
