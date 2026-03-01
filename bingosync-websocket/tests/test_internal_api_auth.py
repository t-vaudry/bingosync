"""
Tests for Tornado internal API authentication.

This module tests that the Tornado server properly validates the X-Internal-Secret
header on internal API endpoints.
"""

import unittest
import sys
import os
from unittest.mock import MagicMock

# Add parent directory to path to import app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import app (environment variables are set in tests/__init__.py)
import app as tornado_app


class ValidateInternalRequestTestCase(unittest.TestCase):
    """Test cases for the validate_internal_request function."""

    def test_validate_internal_request_with_valid_secret(self):
        """Test that validate_internal_request returns True for valid secret."""
        mock_handler = MagicMock()
        mock_handler.request.headers.get.return_value = (
            'test-secret-for-testing-purposes-only-32-chars'
        )

        result = tornado_app.validate_internal_request(mock_handler)
        self.assertTrue(result)

    def test_validate_internal_request_with_invalid_secret(self):
        """Test that validate_internal_request returns False for invalid secret."""
        mock_handler = MagicMock()
        mock_handler.request.headers.get.return_value = 'wrong-secret'

        result = tornado_app.validate_internal_request(mock_handler)
        self.assertFalse(result)

    def test_validate_internal_request_with_missing_header(self):
        """Test that validate_internal_request returns False for missing header."""
        mock_handler = MagicMock()
        mock_handler.request.headers.get.return_value = None

        result = tornado_app.validate_internal_request(mock_handler)
        self.assertFalse(result)

    def test_validate_internal_request_checks_correct_header(self):
        """Test that validate_internal_request checks the X-Internal-Secret header."""
        mock_handler = MagicMock()
        mock_handler.request.headers.get.return_value = (
            'test-secret-for-testing-purposes-only-32-chars'
        )

        tornado_app.validate_internal_request(mock_handler)

        # Verify it checked the correct header name
        mock_handler.request.headers.get.assert_called_once_with(
            'X-Internal-Secret'
        )


class InternalAPISecretConfigTestCase(unittest.TestCase):
    """Test cases for INTERNAL_API_SECRET configuration."""

    def test_internal_api_secret_is_loaded(self):
        """Test that INTERNAL_API_SECRET is loaded from environment."""
        self.assertIsNotNone(tornado_app.INTERNAL_API_SECRET)
        self.assertEqual(
            tornado_app.INTERNAL_API_SECRET,
            'test-secret-for-testing-purposes-only-32-chars'
        )

    def test_internal_api_secret_minimum_length(self):
        """Test that INTERNAL_API_SECRET meets minimum length requirement."""
        self.assertGreaterEqual(len(tornado_app.INTERNAL_API_SECRET), 32)

    def test_internal_api_handler_class_exists(self):
        """Test that InternalAPIHandler class is defined."""
        self.assertTrue(hasattr(tornado_app, 'InternalAPIHandler'))
        self.assertTrue(
            callable(
                getattr(
                    tornado_app.InternalAPIHandler,
                    'prepare',
                    None)))


if __name__ == '__main__':
    unittest.main()
