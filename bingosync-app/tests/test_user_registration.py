"""
Tests for user registration functionality (Task 2.2).
"""
from django.test import TestCase, Client
from django.urls import reverse
from bingosync.models.user import User
from bingosync.forms import UserRegistrationForm


class UserRegistrationFormTests(TestCase):
    """Test the UserRegistrationForm."""
    
    def test_valid_registration_form(self):
        """Test that a valid form passes validation."""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
    
    def test_password_mismatch(self):
        """Test that mismatched passwords fail validation."""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'DifferentPassword123!',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        # Check for the error message (it's HTML escaped in the form errors)
        error_str = str(form.errors)
        self.assertTrue("didn&#x27;t match" in error_str or "didn't match" in error_str)
    
    def test_duplicate_username(self):
        """Test that duplicate usernames are rejected."""
        # Create a user
        User.objects.create_user(username='existinguser', email='existing@example.com', password='password123')
        
        # Try to register with the same username
        form_data = {
            'username': 'existinguser',
            'email': 'new@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
    
    def test_duplicate_email(self):
        """Test that duplicate emails are rejected."""
        # Create a user
        User.objects.create_user(username='user1', email='test@example.com', password='password123')
        
        # Try to register with the same email
        form_data = {
            'username': 'user2',
            'email': 'test@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
    
    def test_weak_password(self):
        """Test that weak passwords are rejected."""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': '123',  # Too short
            'password_confirm': '123',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)
    
    def test_invalid_email(self):
        """Test that invalid email addresses are rejected."""
        form_data = {
            'username': 'testuser',
            'email': 'not-an-email',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
    
    def test_create_user(self):
        """Test that the form creates a user correctly."""
        form_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
        }
        form = UserRegistrationForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        user = form.create_user()
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'newuser')
        self.assertEqual(user.email, 'newuser@example.com')
        self.assertTrue(user.check_password('SecurePassword123!'))
        
        # Verify user statistics are initialized
        self.assertEqual(user.total_games_played, 0)
        self.assertEqual(user.total_squares_marked, 0)
        self.assertEqual(user.total_bingos_completed, 0)


class UserRegistrationViewTests(TestCase):
    """Test the user registration view."""
    
    def setUp(self):
        self.client = Client()
        # Use reverse() to get the correct URL
        self.register_url = reverse('register')
        self.login_url = reverse('login')
    
    def test_registration_page_loads(self):
        """Test that the registration page loads successfully."""
        # Follow redirects to handle APPEND_SLASH middleware
        response = self.client.get(self.register_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register for Bingosync')
        self.assertContains(response, 'username')
        self.assertContains(response, 'email')
        self.assertContains(response, 'password')
    
    def test_successful_registration(self):
        """Test successful user registration."""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
        }
        # POST to the URL using secure=True to simulate HTTPS
        response = self.client.post(self.register_url, data=form_data, follow=False, secure=True)
        
        # Should redirect to login page (302)
        self.assertEqual(response.status_code, 302)
        
        # Verify user was created
        user = User.objects.get(username='testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('SecurePassword123!'))
    
    def test_registration_with_invalid_data(self):
        """Test registration with invalid data."""
        form_data = {
            'username': 'testuser',
            'email': 'invalid-email',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
        }
        # Follow redirects to handle APPEND_SLASH
        response = self.client.post(self.register_url, data=form_data, follow=True)
        
        # Should stay on registration page
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Register for Bingosync')
        
        # Verify user was not created
        self.assertEqual(User.objects.count(), 0)
    
    def test_registration_redirect_to_login(self):
        """Test that successful registration redirects to login page."""
        form_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePassword123!',
            'password_confirm': 'SecurePassword123!',
        }
        # POST and follow redirects using secure=True to simulate HTTPS
        response = self.client.post(self.register_url, data=form_data, follow=True, secure=True)
        
        # Should end up on login page
        # Check for login page content (the actual text in the template)
        self.assertTrue(
            'Login to Bingosync' in response.content.decode() or 
            'Login' in response.content.decode()
        )
        self.assertContains(response, 'Registration successful!')


class UserModelTests(TestCase):
    """Test the User model."""
    
    def test_user_creation(self):
        """Test creating a user."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        self.assertTrue(user.check_password('password123'))
    
    def test_password_hashing(self):
        """Test that passwords are hashed using PBKDF2."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        # Password should be hashed, not stored in plain text
        self.assertNotEqual(user.password, 'password123')
        # Django's default hasher is PBKDF2
        self.assertTrue(user.password.startswith('pbkdf2_sha256$'))
    
    def test_unique_username(self):
        """Test that usernames must be unique."""
        User.objects.create_user(username='testuser', email='test1@example.com', password='password123')
        
        # Try to create another user with the same username
        with self.assertRaises(Exception):
            User.objects.create_user(username='testuser', email='test2@example.com', password='password123')
    
    def test_user_statistics_defaults(self):
        """Test that user statistics are initialized to 0."""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password123'
        )
        self.assertEqual(user.total_games_played, 0)
        self.assertEqual(user.total_squares_marked, 0)
        self.assertEqual(user.total_bingos_completed, 0)
        self.assertEqual(user.wins, 0)
        self.assertEqual(user.losses, 0)
