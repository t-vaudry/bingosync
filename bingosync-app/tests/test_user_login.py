"""
Tests for user login/logout functionality (Task 2.3).
"""
from django.test import TestCase, Client
from django.urls import reverse
from bingosync.models.user import User
from bingosync.forms import UserLoginForm


class UserLoginFormTests(TestCase):
    """Test the UserLoginForm."""

    def test_valid_login_form(self):
        """Test that a valid form passes validation."""
        form_data = {
            'username': 'testuser',
            'password': 'SecurePassword123!',
            'remember_me': False,
        }
        form = UserLoginForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_login_form_with_remember_me(self):
        """Test that remember_me checkbox works."""
        form_data = {
            'username': 'testuser',
            'password': 'SecurePassword123!',
            'remember_me': True,
        }
        form = UserLoginForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertTrue(form.cleaned_data['remember_me'])

    def test_login_form_without_remember_me(self):
        """Test that remember_me is optional."""
        form_data = {
            'username': 'testuser',
            'password': 'SecurePassword123!',
        }
        form = UserLoginForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertFalse(form.cleaned_data['remember_me'])


class UserLoginViewTests(TestCase):
    """Test the user login view."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.rooms_url = reverse('rooms')

        # Ensure URLs have trailing slashes
        if not self.login_url.endswith('/'):
            self.login_url += '/'
        if not self.logout_url.endswith('/'):
            self.logout_url += '/'
        if not self.rooms_url.endswith('/'):
            self.rooms_url += '/'

        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePassword123!'
        )

    def test_login_page_loads(self):
        """Test that the login page loads successfully."""
        response = self.client.get(self.login_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login to Bingosync')
        self.assertContains(response, 'username')
        self.assertContains(response, 'password')

    def test_successful_login(self):
        """Test successful user login."""
        form_data = {
            'username': 'testuser',
            'password': 'SecurePassword123!',
            # Don't include remember_me - it defaults to False
        }
        # Don't follow redirects initially
        response = self.client.post(self.login_url, data=form_data)

        # Check if we got a redirect (could be 301 or 302)
        self.assertIn(response.status_code, [301, 302])

        # Now verify user is logged in by making another request
        response = self.client.get(reverse('rooms'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.username, 'testuser')

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials."""
        form_data = {
            'username': 'testuser',
            'password': 'WrongPassword123!',
            # Don't include remember_me
        }
        response = self.client.post(
            self.login_url, data=form_data, follow=True)

        # Should stay on login page (no redirect to rooms)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Login to Bingosync')

        # Verify user is not logged in
        self.assertFalse(response.wsgi_request.user.is_authenticated)

        # Check that form has errors
        self.assertTrue('form' in response.context)
        self.assertTrue(response.context['form'].errors)

    def test_login_with_nonexistent_user(self):
        """Test login with a username that doesn't exist."""
        form_data = {
            'username': 'nonexistent',
            'password': 'SecurePassword123!',
            # Don't include remember_me
        }
        response = self.client.post(
            self.login_url, data=form_data, follow=True)

        # Should stay on login page (no redirect to rooms)
        self.assertEqual(response.status_code, 200)

        # Verify user is not logged in
        self.assertFalse(response.wsgi_request.user.is_authenticated)

        # Check that form has errors
        self.assertTrue('form' in response.context)
        self.assertTrue(response.context['form'].errors)

    def test_login_with_remember_me(self):
        """Test that remember_me sets session expiry correctly."""
        form_data = {
            'username': 'testuser',
            'password': 'SecurePassword123!',
            'remember_me': True,
        }
        response = self.client.post(
            self.login_url, data=form_data, follow=True)

        # Should redirect to homepage
        self.assertEqual(response.status_code, 200)

        # Check session expiry (2 weeks = 1209600 seconds)
        session = self.client.session
        self.assertEqual(session.get_expiry_age(), 1209600)

    def test_login_without_remember_me(self):
        """Test that session expires when browser closes without remember_me."""
        form_data = {
            'username': 'testuser',
            'password': 'SecurePassword123!',
            # Don't include remember_me - it defaults to False
        }
        response = self.client.post(self.login_url, data=form_data)

        # Should get a redirect (301 or 302)
        self.assertIn(response.status_code, [301, 302])

        # User should be logged in - verify with another request
        response = self.client.get(reverse('rooms'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

        # Session should expire when browser closes
        self.assertTrue(self.client.session.get_expire_at_browser_close())

    def test_logout(self):
        """Test user logout."""
        # First login
        self.client.login(username='testuser', password='SecurePassword123!')

        # Verify user is logged in
        response = self.client.get(self.rooms_url)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

        # Logout
        response = self.client.get(self.logout_url, follow=True)

        # Should redirect to homepage
        self.assertEqual(response.status_code, 200)

        # Verify user is logged out
        response = self.client.get(self.rooms_url)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_logout_when_not_logged_in(self):
        """Test logout when user is not logged in."""
        response = self.client.get(self.logout_url, follow=True)

        # Should still redirect to homepage
        self.assertEqual(response.status_code, 200)

    def test_login_redirect_after_registration(self):
        """Test that login page shows success message after registration."""
        response = self.client.get(
            self.login_url
            + '?registered=true',
            follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registration successful!')
        self.assertContains(response, 'Please login below')


class SessionExpiryTests(TestCase):
    """Test session expiry behavior."""

    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')

        # Ensure URL has trailing slash
        if not self.login_url.endswith('/'):
            self.login_url += '/'

        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePassword123!'
        )

    def test_session_expiry_with_remember_me(self):
        """Test that remember_me sets 2-week session expiry."""
        form_data = {
            'username': 'testuser',
            'password': 'SecurePassword123!',
            'remember_me': True,
        }
        self.client.post(self.login_url, data=form_data)

        # Session should expire in 2 weeks (1209600 seconds)
        session = self.client.session
        self.assertEqual(session.get_expiry_age(), 1209600)

    def test_session_expiry_without_remember_me(self):
        """Test that session expires on browser close without remember_me."""
        form_data = {
            'username': 'testuser',
            'password': 'SecurePassword123!',
            # Don't include remember_me - it defaults to False
        }
        response = self.client.post(self.login_url, data=form_data)

        # Should get a redirect
        self.assertIn(response.status_code, [301, 302])

        # User should be logged in - verify with another request
        response = self.client.get(reverse('rooms'))
        self.assertTrue(response.wsgi_request.user.is_authenticated)

        # Session should expire when browser closes
        self.assertTrue(self.client.session.get_expire_at_browser_close())
