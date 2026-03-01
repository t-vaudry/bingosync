"""
Tests for Django-Tornado shared secret authentication.

This module tests the internal API authentication mechanism that protects
communication between Django and Tornado servers.
"""

from django import test
from django.conf import settings
from unittest.mock import patch, MagicMock

from bingosync.util import get_internal_api_headers
from bingosync.publish import _publish_json


class InternalAPIAuthTestCase(test.TestCase):
    """Test cases for internal API authentication."""

    def test_get_internal_api_headers_includes_secret(self):
        """Test that get_internal_api_headers includes the X-Internal-Secret header."""
        headers = get_internal_api_headers()

        self.assertIn('X-Internal-Secret', headers)
        self.assertEqual(
            headers['X-Internal-Secret'],
            settings.INTERNAL_API_SECRET)
        self.assertIn('Content-Type', headers)
        self.assertEqual(headers['Content-Type'], 'application/json')

    @patch('bingosync.publish.requests.put')
    def test_publish_json_sends_internal_secret(self, mock_put):
        """Test that _publish_json includes the X-Internal-Secret header."""
        # Create a mock room
        mock_room = MagicMock()
        mock_room.encoded_uuid = 'test-room-uuid'

        # Call _publish_json
        test_data = {'type': 'test', 'message': 'hello'}
        _publish_json(test_data, mock_room)

        # Verify requests.put was called with the correct headers
        mock_put.assert_called_once()
        call_args = mock_put.call_args

        # Check that headers were passed
        self.assertIn('headers', call_args.kwargs)
        headers = call_args.kwargs['headers']

        # Verify the X-Internal-Secret header is present
        self.assertIn('X-Internal-Secret', headers)
        self.assertEqual(
            headers['X-Internal-Secret'],
            settings.INTERNAL_API_SECRET)

    def test_internal_api_secret_is_configured(self):
        """Test that INTERNAL_API_SECRET is configured in settings."""
        self.assertIsNotNone(settings.INTERNAL_API_SECRET)
        self.assertGreater(len(settings.INTERNAL_API_SECRET), 0)
