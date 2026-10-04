"""
Tests for the /health endpoint the Django container's healthcheck calls.
"""
from django.test import TestCase


class HealthEndpointTests(TestCase):

    def test_health_returns_ok_without_login(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")
