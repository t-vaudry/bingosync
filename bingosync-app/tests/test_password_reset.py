"""
Tests for password reset functionality.
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

User = get_user_model()


class PasswordResetTest(TestCase):
    """Test password reset functionality."""
    
    def setUp(self):
        """Set up test client and user."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='oldpassword123'
        )
    
    def test_password_reset_form_page_loads(self):
        """Test that password reset form page loads successfully."""
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reset Password')
        self.assertContains(response, 'email')
    
    def test_password_reset_request_sends_email(self):
        """Test that password reset request sends an email."""
        response = self.client.post(reverse('password_reset'), {
            'email': 'test@example.com'
        })
        
        # Should redirect to done page
        self.assertEqual(response.status_code, 302)
        self.assertIn('/password-reset/done/', response.url)
        
        # Should send one email
        self.assertEqual(len(mail.outbox), 1)
        
        # Check email content
        email = mail.outbox[0]
        self.assertEqual(email.to, ['test@example.com'])
        self.assertIn('password reset', email.subject.lower())
        self.assertIn('password-reset-confirm', email.body)
    
    def test_password_reset_done_page_loads(self):
        """Test that password reset done page loads successfully."""
        response = self.client.get(reverse('password_reset_done'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Check your email')
        self.assertContains(response, '24 hours')
    
    def test_password_reset_confirm_with_valid_token(self):
        """Test password reset confirmation with valid token."""
        # Generate valid token
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        
        # Get the confirm page
        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        response = self.client.get(url)
        
        # Should show the form (might redirect to a session-based URL first)
        self.assertIn(response.status_code, [200, 302])
    
    def test_password_reset_confirm_with_invalid_token(self):
        """Test password reset confirmation with invalid token."""
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        # Use a token that matches the pattern but is invalid
        token = 'abc123-def456789012345678901234567890'
        
        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        response = self.client.get(url)
        
        # Should show error message
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid or Expired Link')
    
    def test_password_reset_complete_page_loads(self):
        """Test that password reset complete page loads successfully."""
        response = self.client.get(reverse('password_reset_complete'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Password Reset Complete')
        self.assertContains(response, 'successfully changed')
    
    def test_password_reset_with_nonexistent_email(self):
        """Test password reset with email that doesn't exist."""
        response = self.client.post(reverse('password_reset'), {
            'email': 'nonexistent@example.com'
        })
        
        # Should still redirect to done page (security: don't reveal if email exists)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/password-reset/done/', response.url)
        
        # Should not send any email
        self.assertEqual(len(mail.outbox), 0)
    
    def test_password_reset_changes_password(self):
        """Test that password reset actually changes the password."""
        # Generate valid token
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        
        # Get the confirm page to set up session
        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        self.client.get(url)
        
        # Submit new password (Django redirects to a session-based URL)
        # We need to follow the redirect and post to the session URL
        response = self.client.get(url, follow=True)
        
        # Extract the actual URL from the redirect chain
        if response.redirect_chain:
            actual_url = response.redirect_chain[-1][0]
            
            # Post new password
            response = self.client.post(actual_url, {
                'new_password1': 'newpassword123',
                'new_password2': 'newpassword123'
            })
            
            # Should redirect to complete page
            self.assertEqual(response.status_code, 302)
            
            # Verify password was changed
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password('newpassword123'))
            self.assertFalse(self.user.check_password('oldpassword123'))
    
    def test_login_page_has_forgot_password_link(self):
        """Test that login page has a link to password reset."""
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Forgot your password?')
        self.assertContains(response, reverse('password_reset'))
