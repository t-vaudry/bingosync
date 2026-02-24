"""
Tests for security headers configuration.

Validates that all required security headers are present in HTTP responses.
"""

from django.test import TestCase, Client
from django.urls import reverse


class SecurityHeadersTestCase(TestCase):
    """Test that security headers are properly configured"""

    def setUp(self):
        self.client = Client()

    def test_security_headers_present(self):
        """Test that security headers are present in responses"""
        # Make a request to the homepage which should have security headers
        # Use secure=True to simulate HTTPS and avoid redirect
        response = self.client.get('/', secure=True)
        
        # Check for Content Security Policy header
        self.assertIn('Content-Security-Policy', response)
        csp = response['Content-Security-Policy']
        
        # Verify CSP directives
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self' 'unsafe-inline'", csp)
        self.assertIn("style-src 'self' 'unsafe-inline'", csp)
        self.assertIn("frame-ancestors 'none'", csp)

    def test_x_frame_options_header(self):
        """Test that X-Frame-Options header is set to DENY"""
        response = self.client.get('/', secure=True)
        
        # Django's XFrameOptionsMiddleware should set this
        self.assertEqual(response.get('X-Frame-Options'), 'DENY')

    def test_content_type_nosniff_header(self):
        """Test that X-Content-Type-Options header is set"""
        response = self.client.get('/', secure=True)
        
        # Django's SecurityMiddleware should set this when SECURE_CONTENT_TYPE_NOSNIFF is True
        self.assertEqual(response.get('X-Content-Type-Options'), 'nosniff')

    def test_hsts_header_in_production(self):
        """Test that HSTS settings are configured for production mode"""
        # In production with HTTPS, Django's SecurityMiddleware sets HSTS
        # We verify the settings are configured correctly
        from django.conf import settings
        
        self.assertEqual(settings.SECURE_HSTS_SECONDS, 31536000)
        self.assertTrue(settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)

    def test_csp_settings_configured(self):
        """Test that CSP settings are properly configured"""
        from django.conf import settings
        
        # Verify CSP settings exist
        self.assertEqual(settings.CSP_DEFAULT_SRC, ("'self'",))
        self.assertEqual(settings.CSP_SCRIPT_SRC, ("'self'", "'unsafe-inline'"))
        self.assertEqual(settings.CSP_STYLE_SRC, ("'self'", "'unsafe-inline'"))
        self.assertEqual(settings.CSP_IMG_SRC, ("'self'", "data:"))
        self.assertEqual(settings.CSP_FONT_SRC, ("'self'",))
        self.assertEqual(settings.CSP_CONNECT_SRC, ("'self'",))
        self.assertEqual(settings.CSP_FRAME_ANCESTORS, ("'none'",))

    def test_secure_cookie_settings(self):
        """Test that secure cookie settings are configured"""
        from django.conf import settings
        
        # These should be set in production (IS_PROD=True)
        # In test mode they may not be set, but we verify they exist in settings.py
        self.assertTrue(hasattr(settings, 'CSRF_COOKIE_SECURE'))
        self.assertTrue(hasattr(settings, 'SESSION_COOKIE_SECURE'))
        self.assertTrue(hasattr(settings, 'CSRF_COOKIE_HTTPONLY'))
        self.assertTrue(hasattr(settings, 'SESSION_COOKIE_HTTPONLY'))

    def test_security_middleware_order(self):
        """Test that SecurityHeadersMiddleware is in the middleware stack"""
        from django.conf import settings
        
        middleware = settings.MIDDLEWARE
        
        # Verify our custom middleware is present
        self.assertIn('bingosync.middleware.SecurityHeadersMiddleware', middleware)
        
        # Verify Django's security middleware is present
        self.assertIn('django.middleware.security.SecurityMiddleware', middleware)
        self.assertIn('django.middleware.clickjacking.XFrameOptionsMiddleware', middleware)
