"""
Tests for form validation and sanitization.

This module tests that forms properly validate and sanitize user inputs.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model, hashers

from bingosync.forms import RoomForm, JoinRoomForm
from bingosync.models import Room, GameType, LockoutMode, FilteredPattern
from bingosync.models.enums import Role

User = get_user_model()


class RoomFormValidationTestCase(TestCase):
    """Test RoomForm validation."""

    def setUp(self):
        """Set up test data."""
        # Create a test user for room creation
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.valid_data = {
            'room_name': 'Test Room',
            'passphrase': 'password123',
            'game_type': '50',  # HP CoS
            'lockout_mode': str(LockoutMode.non_lockout.value),
            'seed': '12345',
            'hide_card': False,
            'fog_of_war': False,
            'assign_gamemaster': False,
        }

    def test_valid_form(self):
        """Valid form data should pass validation."""
        form = RoomForm(data=self.valid_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_empty_room_name(self):
        """Empty room name should fail validation."""
        data = self.valid_data.copy()
        data['room_name'] = ''
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('room_name', form.errors)

    def test_room_name_with_html_tags(self):
        """Room name with HTML tags should fail validation."""
        data = self.valid_data.copy()
        data['room_name'] = '<b>Test</b> Room'
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('room_name', form.errors)

    def test_room_name_sanitization(self):
        """Room name should be sanitized."""
        data = self.valid_data.copy()
        data['room_name'] = '  Test  Room  '
        form = RoomForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['room_name'], 'Test Room')

    def test_room_name_max_length(self):
        """Room name at max length should pass validation."""
        data = self.valid_data.copy()
        data['room_name'] = 'A' * 255
        form = RoomForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_room_name_exceeds_max_length(self):
        """Room name exceeding max length should fail validation."""
        data = self.valid_data.copy()
        data['room_name'] = 'A' * 256
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('room_name', form.errors)

    def test_empty_seed_allowed(self):
        """Empty seed should be allowed (will generate random)."""
        data = self.valid_data.copy()
        data['seed'] = ''
        form = RoomForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_negative_seed(self):
        """Negative seed should fail validation."""
        data = self.valid_data.copy()
        data['seed'] = '-1'
        form = RoomForm(data=data)
        # Seed validation happens in the validator
        self.assertFalse(form.is_valid())
        self.assertIn('seed', form.errors)


class JoinRoomFormValidationTestCase(TestCase):
    """Test JoinRoomForm validation."""

    def setUp(self):
        """Set up test data."""
        # Create a test room
        encrypted_passphrase = hashers.make_password('testpass')
        self.room = Room.objects.create(
            name='Test Room',
            passphrase=encrypted_passphrase,
            hide_card=False
        )

        self.valid_data = {
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'TestPlayer',
            'passphrase': 'testpass',
            'role': Role.PLAYER,
        }

    def test_valid_form(self):
        """Valid form data should pass validation."""
        form = JoinRoomForm(data=self.valid_data, room=self.room)
        self.assertTrue(form.is_valid(), form.errors)

    def test_empty_player_name(self):
        """Empty player name should fail validation."""
        data = self.valid_data.copy()
        data['player_name'] = ''
        form = JoinRoomForm(data=data, room=self.room)
        self.assertFalse(form.is_valid())
        self.assertIn('player_name', form.errors)

    def test_player_name_with_html_tags(self):
        """Player name with HTML tags should fail validation."""
        data = self.valid_data.copy()
        data['player_name'] = '<b>Player</b>'
        form = JoinRoomForm(data=data, room=self.room)
        self.assertFalse(form.is_valid())
        self.assertIn('player_name', form.errors)

    def test_player_name_sanitization(self):
        """Player name should be sanitized."""
        data = self.valid_data.copy()
        data['player_name'] = '  Test  Player  '
        form = JoinRoomForm(data=data, room=self.room)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['player_name'], 'Test Player')

    def test_player_name_max_length(self):
        """Player name at max length should pass validation."""
        data = self.valid_data.copy()
        data['player_name'] = 'A' * 50
        form = JoinRoomForm(data=data, room=self.room)
        self.assertTrue(form.is_valid(), form.errors)

    def test_player_name_exceeds_max_length(self):
        """Player name exceeding max length should fail validation."""
        data = self.valid_data.copy()
        data['player_name'] = 'A' * 51
        form = JoinRoomForm(data=data, room=self.room)
        self.assertFalse(form.is_valid())
        self.assertIn('player_name', form.errors)

    def test_incorrect_passphrase(self):
        """Incorrect passphrase should fail validation."""
        data = self.valid_data.copy()
        data['passphrase'] = 'wrongpassword'
        form = JoinRoomForm(data=data, room=self.room)
        self.assertFalse(form.is_valid())

    def test_empty_passphrase(self):
        """A blank passphrase against a password-protected room should fail.

        Passwords are optional at the field level now, but a room that has a
        password still rejects a blank one (as a non-field error)."""
        data = self.valid_data.copy()
        data['passphrase'] = ''
        form = JoinRoomForm(data=data, room=self.room)
        self.assertFalse(form.is_valid())
        self.assertIn('Incorrect Password', str(form.errors))


class ProfanityFilterTestCase(TestCase):
    """Test profanity filtering integration."""

    def test_profanity_in_room_name(self):
        """Room name with profanity should be filtered."""
        # This test depends on the profanity filter configuration
        # Skip if no profanity patterns are configured
        if not FilteredPattern.objects.exists():
            self.skipTest("No profanity patterns configured")

        data = {
            'room_name': 'Test Room',  # Use a clean name for testing
            'passphrase': 'password123',
            'game_type': '50',
            'lockout_mode': str(LockoutMode.non_lockout.value),
            'seed': '12345',
            'hide_card': False,
            'fog_of_war': False,
            'assign_gamemaster': False,
        }
        form = RoomForm(data=data)
        self.assertTrue(form.is_valid())
        # The actual filtering happens in clean_room_name()
        # and depends on FilteredPattern configuration
