"""
Tests for WebSocket origin validation.

This module tests that the WebSocket server properly validates the Origin header
against ALLOWED_HOSTS configuration.
"""

import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add parent directory to path to import app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import app (environment variables are set in tests/__init__.py)
import app as tornado_app


class WebSocketOriginValidationTestCase(unittest.TestCase):
    """Test cases for WebSocket origin validation."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock WebSocket handler
        self.ws_handler = tornado_app.BroadcastWebSocket(
            application=MagicMock(),
            request=MagicMock()
        )
        self.ws_handler.request.remote_ip = '192.168.1.1'

    def test_allowed_hosts_configuration(self):
        """Test that ALLOWED_HOSTS is properly configured."""
        self.assertIn('127.0.0.1', tornado_app.ALLOWED_HOSTS)
        self.assertIn('localhost', tornado_app.ALLOWED_HOSTS)
        self.assertIn('example.com', tornado_app.ALLOWED_HOSTS)

    def test_check_origin_accepts_localhost(self):
        """Test that check_origin accepts connections from localhost."""
        result = self.ws_handler.check_origin('http://localhost:8000')
        self.assertTrue(result)

    def test_check_origin_accepts_127_0_0_1(self):
        """Test that check_origin accepts connections from 127.0.0.1."""
        result = self.ws_handler.check_origin('http://127.0.0.1:8000')
        self.assertTrue(result)

    def test_check_origin_accepts_configured_domain(self):
        """Test that check_origin accepts connections from configured DOMAIN."""
        result = self.ws_handler.check_origin('https://example.com')
        self.assertTrue(result)

    def test_check_origin_rejects_unauthorized_domain(self):
        """Test that check_origin rejects connections from unauthorized domains."""
        result = self.ws_handler.check_origin('https://malicious.com')
        self.assertFalse(result)

    def test_check_origin_rejects_unauthorized_subdomain(self):
        """Test that check_origin rejects connections from unauthorized subdomains."""
        result = self.ws_handler.check_origin('https://evil.example.com')
        self.assertFalse(result)

    @patch('builtins.print')
    def test_check_origin_logs_rejected_connection(self, mock_print):
        """Test that check_origin logs rejected connections."""
        self.ws_handler.check_origin('https://malicious.com')

        # Verify that a log message was printed
        mock_print.assert_called()
        call_args = str(mock_print.call_args)
        self.assertIn('rejected', call_args.lower())
        self.assertIn('malicious.com', call_args)

    def test_check_origin_handles_https_protocol(self):
        """Test that check_origin handles HTTPS origins correctly."""
        result = self.ws_handler.check_origin('https://localhost:8000')
        self.assertTrue(result)

    def test_check_origin_handles_http_protocol(self):
        """Test that check_origin handles HTTP origins correctly."""
        result = self.ws_handler.check_origin('http://localhost:8000')
        self.assertTrue(result)

    def test_check_origin_handles_port_numbers(self):
        """Test that check_origin correctly handles port numbers in origin."""
        result = self.ws_handler.check_origin('http://localhost:3000')
        self.assertTrue(result)

    @patch('builtins.print')
    def test_check_origin_handles_invalid_origin_format(self, mock_print):
        """Test that check_origin handles invalid origin formats gracefully."""
        result = self.ws_handler.check_origin('not-a-valid-url')
        self.assertFalse(result)

        # Verify that an error was logged
        mock_print.assert_called()
        call_args = str(mock_print.call_args)
        self.assertIn('rejected', call_args.lower())

    def test_check_origin_case_sensitivity(self):
        """Test that check_origin handles hostname case correctly."""
        # Hostnames should be case-insensitive, but urllib.parse.urlparse
        # returns lowercase hostnames
        result = self.ws_handler.check_origin('http://LOCALHOST:8000')
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()
