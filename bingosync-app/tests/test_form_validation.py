"""
Tests for form validation and sanitization.

This module tests that forms properly validate and sanitize user inputs.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError

from bingosync.forms import RoomForm, JoinRoomForm
from bingosync.models import Room, GameType, LockoutMode, FilteredPattern
from bingosync.models.enums import Role
from django.contrib.auth import hashers


class RoomFormValidationTestCase(TestCase):
    """Test RoomForm validation."""

    def setUp(self):
        """Set up test data."""
        # Get a valid game type value
        game_choices = GameType.game_choices()
        if game_choices:
            game_type_value = str(game_choices[0][0])
        else:
            game_type_value = '1'  # Fallback
        
        self.valid_data = {
            'room_name': 'Test Room',
            'passphrase': 'password123',
            'nickname': 'TestPlayer',
            'game_type': game_type_value,
            'lockout_mode': str(LockoutMode.non_lockout.value),
            'seed': '12345',
            'size': '5',
            'is_spectator': False,
            'hide_card': False,
            'fog_of_war': False,
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

    def test_whitespace_only_room_name(self):
        """Whitespace-only room name should fail validation."""
        data = self.valid_data.copy()
        data['room_name'] = '   '
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('room_name', form.errors)

    def test_room_name_with_html_tags(self):
        """Room name with HTML tags should fail validation."""
        data = self.valid_data.copy()
        data['room_name'] = '<script>alert("xss")</script>'
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

    def test_empty_nickname(self):
        """Empty nickname should fail validation."""
        data = self.valid_data.copy()
        data['nickname'] = ''
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('nickname', form.errors)

    def test_nickname_with_html_tags(self):
        """Nickname with HTML tags should fail validation."""
        data = self.valid_data.copy()
        data['nickname'] = '<b>Player</b>'
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('nickname', form.errors)

    def test_nickname_sanitization(self):
        """Nickname should be sanitized."""
        data = self.valid_data.copy()
        data['nickname'] = '  Test  Player  '
        form = RoomForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['nickname'], 'Test Player')

    def test_empty_passphrase(self):
        """Empty passphrase should fail validation."""
        data = self.valid_data.copy()
        data['passphrase'] = ''
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('passphrase', form.errors)

    def test_negative_seed(self):
        """Negative seed should fail validation."""
        data = self.valid_data.copy()
        data['seed'] = '-1'
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('seed', form.errors)

    def test_non_numeric_seed(self):
        """Non-numeric seed should fail validation."""
        data = self.valid_data.copy()
        data['seed'] = 'abc'
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('seed', form.errors)

    def test_empty_seed_allowed(self):
        """Empty seed should be allowed (will be randomized)."""
        data = self.valid_data.copy()
        data['seed'] = ''
        form = RoomForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_zero_board_size(self):
        """Zero board size should fail validation."""
        data = self.valid_data.copy()
        data['size'] = '0'
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('size', form.errors)

    def test_negative_board_size(self):
        """Negative board size should fail validation."""
        data = self.valid_data.copy()
        data['size'] = '-1'
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('size', form.errors)

    def test_empty_board_size_allowed(self):
        """Empty board size should be allowed (will use default)."""
        data = self.valid_data.copy()
        data['size'] = ''
        form = RoomForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

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

    def test_nickname_max_length(self):
        """Nickname at max length should pass validation."""
        data = self.valid_data.copy()
        data['nickname'] = 'A' * 50
        form = RoomForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_nickname_exceeds_max_length(self):
        """Nickname exceeding max length should fail validation."""
        data = self.valid_data.copy()
        data['nickname'] = 'A' * 51
        form = RoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('nickname', form.errors)


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
            'room_name': self.room.name,
            'creator_name': 'Creator',
            'game_name': 'Test Game',
            'player_name': 'TestPlayer',
            'passphrase': 'testpass',
            'role': Role.PLAYER,
        }

    def test_valid_form(self):
        """Valid form data should pass validation."""
        form = JoinRoomForm(data=self.valid_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_empty_player_name(self):
        """Empty player name should fail validation."""
        data = self.valid_data.copy()
        data['player_name'] = ''
        form = JoinRoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('player_name', form.errors)

    def test_player_name_with_html_tags(self):
        """Player name with HTML tags should fail validation."""
        data = self.valid_data.copy()
        data['player_name'] = '<script>alert("xss")</script>'
        form = JoinRoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('player_name', form.errors)

    def test_player_name_sanitization(self):
        """Player name should be sanitized."""
        data = self.valid_data.copy()
        data['player_name'] = '  Test  Player  '
        form = JoinRoomForm(data=data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['player_name'], 'Test Player')

    def test_incorrect_passphrase(self):
        """Incorrect passphrase should fail validation."""
        data = self.valid_data.copy()
        data['passphrase'] = 'wrongpass'
        form = JoinRoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)

    def test_empty_passphrase(self):
        """Empty passphrase should fail validation."""
        data = self.valid_data.copy()
        data['passphrase'] = ''
        form = JoinRoomForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('passphrase', form.errors)


class ProfanityFilterTestCase(TestCase):
    """Test profanity filtering integration."""

    def setUp(self):
        """Set up test data with profanity patterns."""
        # Create a test profanity pattern
        FilteredPattern.objects.create(pattern=r'\bbadword\b')
        
        # Get a valid game type value
        game_choices = GameType.game_choices()
        if game_choices:
            game_type_value = str(game_choices[0][0])
        else:
            game_type_value = '1'  # Fallback
        
        self.valid_data = {
            'room_name': 'Test Room',
            'passphrase': 'password123',
            'nickname': 'TestPlayer',
            'game_type': game_type_value,
            'lockout_mode': str(LockoutMode.non_lockout.value),
            'seed': '12345',
            'size': '5',
            'is_spectator': False,
            'hide_card': False,
            'fog_of_war': False,
        }

    def test_profanity_filter_applied_to_room_name(self):
        """Profanity filter should be applied to room name."""
        data = self.valid_data.copy()
        data['room_name'] = 'Room with badword in it'
        form = RoomForm(data=data)
        self.assertTrue(form.is_valid())
        # The word should be replaced with "bingo"
        self.assertIn('bingo', form.cleaned_data['room_name'])
        self.assertNotIn('badword', form.cleaned_data['room_name'])

    def test_profanity_filter_applied_to_nickname(self):
        """Profanity filter should be applied to nickname."""
        data = self.valid_data.copy()
        data['nickname'] = 'badword player'
        form = RoomForm(data=data)
        self.assertTrue(form.is_valid())
        # The word should be replaced with "bingo"
        self.assertIn('bingo', form.cleaned_data['nickname'])
        self.assertNotIn('badword', form.cleaned_data['nickname'])
