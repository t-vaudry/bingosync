"""
Tests for authentication enforcement in room creation and joining.

This module tests that:
- Room creation requires authentication for non-spectators
- Joining as Player/Counter requires authentication
- Joining as Spectator does NOT require authentication
- Authenticated users have their username automatically set as nickname
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from bingosync.models.rooms import Room, Player
from bingosync.models.enums import Role
from bingosync.forms import RoomForm, JoinRoomForm
from django.core.exceptions import ValidationError

User = get_user_model()


class AuthenticationEnforcementTest(TestCase):
    """Test authentication requirements for room creation and joining."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_room_creation_requires_auth_for_gamemaster(self):
        """Test that creating a room as Gamemaster requires authentication."""
        form_data = {
            'room_name': 'Test Room',
            'passphrase': 'testpass',
            'nickname': 'TestNick',
            'lockout_mode': '1',
            'is_spectator': False,
            'gamemaster_only': False,
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data, user=None)
        self.assertTrue(form.is_valid())

        # Should raise ValidationError when trying to create without auth
        with self.assertRaises(ValidationError) as context:
            form.create_room(user=None)

        self.assertIn('must be logged in', str(context.exception))

    def test_room_creation_allows_spectator_without_auth(self):
        """Test that creating a room as Spectator does NOT require authentication."""
        form_data = {
            'room_name': 'Test Room',
            'passphrase': 'testpass',
            'nickname': 'TestNick',
            'lockout_mode': '1',
            'is_spectator': True,
            'gamemaster_only': False,
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data, user=None)
        self.assertTrue(form.is_valid())

        # Should succeed for spectator without auth
        room = form.create_room(user=None)
        self.assertIsNotNone(room)
        self.assertEqual(room.creator.role, Role.SPECTATOR)
        self.assertIsNone(room.creator.user)

    def test_room_creation_uses_username_for_authenticated_user(self):
        """Test that authenticated users have their username set as nickname."""
        form_data = {
            'room_name': 'Test Room',
            'passphrase': 'testpass',
            'nickname': 'IgnoredNick',  # This should be ignored
            'lockout_mode': '1',
            'is_spectator': False,
            'gamemaster_only': False,
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())

        room = form.create_room(user=self.user)
        self.assertEqual(room.creator.name, 'testuser')
        self.assertEqual(room.creator.user, self.user)

    def test_join_as_player_requires_auth(self):
        """Test that joining as Player requires authentication."""
        # Create a room first
        room = self._create_test_room()

        form_data = {
            'encoded_room_uuid': room.encoded_uuid,
            'player_name': 'TestPlayer',
            'passphrase': 'testpass',
            'role': Role.PLAYER,
        }
        form = JoinRoomForm(data=form_data, room=room, user=None)
        self.assertTrue(form.is_valid())

        # Should raise ValidationError when trying to join as Player without auth
        with self.assertRaises(ValidationError) as context:
            form.create_player(user=None)

        self.assertIn('must be logged in', str(context.exception))

    def test_join_as_counter_requires_auth(self):
        """Test that joining as Counter requires authentication."""
        # Create a room first
        room = self._create_test_room()

        form_data = {
            'encoded_room_uuid': room.encoded_uuid,
            'player_name': 'TestCounter',
            'passphrase': 'testpass',
            'role': Role.COUNTER,
        }
        form = JoinRoomForm(data=form_data, room=room, user=None)
        self.assertTrue(form.is_valid())

        # Should raise ValidationError when trying to join as Counter without auth
        with self.assertRaises(ValidationError) as context:
            form.create_player(user=None)

        self.assertIn('must be logged in', str(context.exception))

    def test_join_as_spectator_allows_anonymous(self):
        """Test that joining as Spectator does NOT require authentication."""
        # Create a room first
        room = self._create_test_room()

        form_data = {
            'encoded_room_uuid': room.encoded_uuid,
            'player_name': 'AnonSpectator',
            'passphrase': 'testpass',
            'role': Role.SPECTATOR,
        }
        form = JoinRoomForm(data=form_data, room=room, user=None)
        self.assertTrue(form.is_valid())

        # Should succeed for spectator without auth
        player = form.create_player(user=None)
        self.assertIsNotNone(player)
        self.assertEqual(player.role, Role.SPECTATOR)
        self.assertIsNone(player.user)
        self.assertEqual(player.name, 'AnonSpectator')

    def test_join_uses_username_for_authenticated_user(self):
        """Test that authenticated users have their username set as nickname when joining."""
        # Create a room first
        room = self._create_test_room()

        form_data = {
            'encoded_room_uuid': room.encoded_uuid,
            'player_name': 'IgnoredNick',  # This should be ignored
            'passphrase': 'testpass',
            'role': Role.PLAYER,
        }
        form = JoinRoomForm(data=form_data, room=room, user=self.user)
        self.assertTrue(form.is_valid())

        player = form.create_player(user=self.user)
        self.assertEqual(player.name, 'testuser')
        self.assertEqual(player.user, self.user)

    def test_player_user_field_nullable(self):
        """Test that Player.user field is nullable for anonymous spectators."""
        room = self._create_test_room()

        # Create anonymous spectator
        spectator = Player.objects.create(
            room=room,
            name='AnonSpectator',
            role=Role.SPECTATOR,
            user=None
        )
        self.assertIsNone(spectator.user)

        # Create authenticated player
        player = Player.objects.create(
            room=room,
            name='AuthPlayer',
            role=Role.PLAYER,
            user=self.user
        )
        self.assertEqual(player.user, self.user)

    def _create_test_room(self):
        """Helper method to create a test room."""
        from django.contrib.auth.hashers import make_password
        from bingosync.models.rooms import Game
        from bingosync.models.game_type import GameType

        room = Room.objects.create(
            name='Test Room',
            passphrase=make_password('testpass'),
            hide_card=False
        )

        # Create a game for the room
        game_type = GameType.for_value(50)  # HP CoS
        seed, board_json = game_type.generator_instance().get_card('12345', [], 5)
        Game.from_board(
            board_json,
            room=room,
            game_type_value=50,
            lockout_mode_value=1,
            seed=seed,
            fog_of_war=False
        )

        return room
