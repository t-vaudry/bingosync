"""
Tests for authentication enforcement in room creation and joining.

This module tests that:
- Anyone can create a room (anonymously, under a nickname)
- Anyone can join as Player, Counter or Spectator
- Anonymous players have no user attached, so nothing is tracked for them
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

    def test_room_creation_without_account_uses_nickname(self):
        """Someone without an account can create a room under a nickname."""
        form_data = {
            'room_name': 'Test Room',
            'passphrase': 'testpass',
            'player_name': '  Anon   Host ',
            'lockout_mode': '1',
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data, user=None, anonymous=True)
        self.assertTrue(form.is_valid(), form.errors)

        room = form.create_room(user=None)
        self.assertEqual(room.creator.role, Role.PLAYER)
        self.assertEqual(room.creator.name, 'Anon Host')
        self.assertIsNone(room.creator.user)

    def test_room_creation_without_account_requires_nickname(self):
        form_data = {
            'room_name': 'Test Room',
            'passphrase': 'testpass',
            'lockout_mode': '1',
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data, user=None, anonymous=True)
        self.assertFalse(form.is_valid())
        self.assertIn('player_name', form.errors)

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

    def test_join_as_player_or_counter_allows_anonymous(self):
        """Players and Counters don't need an account either."""
        room = self._create_test_room()

        for role in (Role.PLAYER, Role.COUNTER):
            form = JoinRoomForm(data={
                'encoded_room_uuid': room.encoded_uuid,
                'player_name': 'Anon ' + role,
                'passphrase': 'testpass',
                'role': role,
            }, room=room, user=None)
            self.assertTrue(form.is_valid())
            player = form.create_player(user=None)
            self.assertEqual(player.role, role)
            self.assertIsNone(player.user)

    def test_anonymous_cannot_use_a_registered_username(self):
        room = self._create_test_room()
        form = JoinRoomForm(data={
            'encoded_room_uuid': room.encoded_uuid,
            'player_name': 'TestUser',
            'passphrase': 'testpass',
            'role': Role.PLAYER,
        }, room=room, user=None)
        self.assertTrue(form.is_valid())
        with self.assertRaises(ValidationError):
            form.create_player(user=None)

    def test_landing_has_no_global_stats_and_explains_accounts(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'Global Stats')
        self.assertContains(resp, 'Do you need an account?')

    def test_home_open_to_anonymous(self):
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="player_name"')

    def test_anonymous_can_create_room_from_home(self):
        resp = self.client.post('/', {
            'room_name': 'Anon Room',
            'passphrase': '',
            'player_name': 'Hosty',
            'lockout_mode': '1',
        })
        self.assertEqual(resp.status_code, 302, getattr(resp, 'context', None))
        room = Room.objects.get(name='Anon Room')
        self.assertEqual(room.creator.name, 'Hosty')
        self.assertIsNone(room.creator.user)
        # and they're in it
        resp = self.client.get(f'/room/{room.encoded_uuid}')
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, 'id="copy-obs-link"')

    def test_anonymous_can_join_by_code_as_player(self):
        room = self._create_test_room()
        resp = self.client.post('/join-room', {
            'room_code': room.room_code,
            'password': 'testpass',
            'display_name': 'Guest',
            'role': 'player',
        })
        self.assertEqual(resp.status_code, 302)
        player = room.players.get(name='Guest')
        self.assertEqual(player.role, Role.PLAYER)
        self.assertIsNone(player.user)

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
            room_code=Room.generate_room_code(),
            active=True,
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
