"""
Integration tests for role-based permissions in views.
"""

import json
from unittest.mock import patch
from django.test import TestCase, Client
from bingosync.models import Room, Player, Game, User
from bingosync.models.enums import Role
from bingosync.models.game_type import GameType
from bingosync.models.rooms import LockoutMode


@patch('bingosync.publish.requests.put')
class PermissionIntegrationTestCase(TestCase):
    """Test permission enforcement in views."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create a room with a game
        self.room = Room.objects.create(
            name='Test Room',
            passphrase='test123'
        )

        # Create a game for the room
        board_json = [{"name": f"Goal {i}", "tier": 1} for i in range(1, 26)]
        self.game = Game.from_board(
            board_json,
            room=self.room,
            seed=12345,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=LockoutMode.non_lockout.value
        )

    def _create_player_session(self, player):
        """Helper to create a session with player authentication."""
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: player.encoded_uuid
        }
        session.save()

    def test_spectator_cannot_mark_square(self, mock_put):
        """Test that spectators cannot mark squares."""
        # Create spectator player
        spectator = Player.objects.create(
            room=self.room,
            name='Spectator',
            role=Role.SPECTATOR
        )

        # Set up session
        self._create_player_session(spectator)

        # Try to mark a square
        response = self.client.post(
            '/api/select',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': 1,
                'color': 'red',
                'remove_color': False
            }),
            content_type='application/json'
        )

        # Should be forbidden
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'permission', response.content.lower())

    def test_player_can_mark_square(self, mock_put):
        """Test that players can mark squares."""
        # Create player
        player = Player.objects.create(
            room=self.room,
            name='Player',
            role=Role.PLAYER
        )

        # Set up session
        self._create_player_session(player)

        # Try to mark a square
        response = self.client.post(
            '/api/select',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': 1,
                'color': 'red',
                'remove_color': False
            }),
            content_type='application/json'
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)

    def test_gamemaster_only_cannot_mark_square(self, mock_put):
        """Test that GM-only cannot mark squares."""
        # Create GM-only player
        gm = Player.objects.create(
            room=self.room,
            name='Gamemaster',
            role=Role.GAMEMASTER,
            is_also_player=False
        )

        # Set up session
        self._create_player_session(gm)

        # Try to mark a square
        response = self.client.post(
            '/api/select',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': 1,
                'color': 'red',
                'remove_color': False
            }),
            content_type='application/json'
        )

        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_gamemaster_player_can_mark_square(self, mock_put):
        """Test that GM+Player can mark squares."""
        # Create GM+Player
        gm_player = Player.objects.create(
            room=self.room,
            name='GM+Player',
            role=Role.GAMEMASTER,
            is_also_player=True
        )

        # Set up session
        self._create_player_session(gm_player)

        # Try to mark a square
        response = self.client.post(
            '/api/select',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': 1,
                'color': 'red',
                'remove_color': False
            }),
            content_type='application/json'
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)

    def test_player_cannot_generate_board(self, mock_put):
        """Test that regular players cannot generate new boards."""
        # Create player
        player = Player.objects.create(
            room=self.room,
            name='Player',
            role=Role.PLAYER
        )

        # Set up session
        self._create_player_session(player)

        # Try to generate new board
        response = self.client.put(
            '/api/new-card',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'seed': '54321',
                'game_type': str(GameType.hp_cos.value),
                'lockout_mode': str(LockoutMode.non_lockout.value),
                'hide_card': False,
                'fog_of_war': 'off',
                'size': 5
            }),
            content_type='application/json'
        )

        # Should be forbidden
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'permission', response.content.lower())

    def test_gamemaster_can_generate_board(self, mock_put):
        """Test that gamemasters can generate new boards."""
        # Create GM
        gm = Player.objects.create(
            room=self.room,
            name='Gamemaster',
            role=Role.GAMEMASTER,
            is_also_player=False
        )

        # Set up session
        self._create_player_session(gm)

        # Try to generate new board
        response = self.client.put(
            '/api/new-card',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'seed': '54321',
                'game_type': str(GameType.hp_cos.value),
                'lockout_mode': str(LockoutMode.non_lockout.value),
                'hide_card': False,
                'fog_of_war': 'off',
                'size': 5
            }),
            content_type='application/json'
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)

    def test_player_cannot_reveal_board(self, mock_put):
        """Test that regular players cannot reveal fog of war."""
        # Create player
        player = Player.objects.create(
            room=self.room,
            name='Player',
            role=Role.PLAYER
        )

        # Set up session
        self._create_player_session(player)

        # Try to reveal board
        response = self.client.post(
            '/api/revealed',
            data=json.dumps({
                'room': self.room.encoded_uuid
            }),
            content_type='application/json'
        )

        # Should be forbidden
        self.assertEqual(response.status_code, 403)
        self.assertIn(b'permission', response.content.lower())

    def test_gamemaster_can_reveal_board(self, mock_put):
        """Test that gamemasters can reveal fog of war."""
        # Create GM
        gm = Player.objects.create(
            room=self.room,
            name='Gamemaster',
            role=Role.GAMEMASTER,
            is_also_player=False
        )

        # Set up session
        self._create_player_session(gm)

        # Try to reveal board
        response = self.client.post(
            '/api/revealed',
            data=json.dumps({
                'room': self.room.encoded_uuid
            }),
            content_type='application/json'
        )

        # Should succeed
        self.assertEqual(response.status_code, 200)
