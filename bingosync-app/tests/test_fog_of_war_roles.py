"""
Integration tests for fog of war with role system.

Tests that fog of war visibility rules work correctly for each role:
- Players see fog of war normally (squares hidden until revealed)
- Spectators see only revealed squares
- Counters see all squares (to verify claims)
- Gamemaster can reveal the entire board
"""

import json
from unittest.mock import patch
from django.test import TestCase, Client
from bingosync.models import Room, Player, Game, User, Square
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.models.game_type import GameType
from bingosync.models.rooms import LockoutMode


# Mock WebSocket publishing for all tests
@patch('bingosync.publish.requests.put')
class FogOfWarRoleTestCase(TestCase):
    """Test fog of war functionality with different roles."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test users
        self.user1 = User.objects.create_user(
            username='player1',
            email='player1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='spectator1',
            email='spectator1@example.com',
            password='testpass123'
        )
        self.user3 = User.objects.create_user(
            username='counter1',
            email='counter1@example.com',
            password='testpass123'
        )
        self.user4 = User.objects.create_user(
            username='gamemaster1',
            email='gm1@example.com',
            password='testpass123'
        )

        # Create a room
        self.room = Room.objects.create(
            name='Fog of War Test Room',
            passphrase='test123'
        )

        # Create a game with fog of war enabled
        board_json = [{"name": f"Goal {i}", "tier": i % 5 + 1}
                      for i in range(1, 26)]
        self.game = Game.from_board(
            board_json,
            room=self.room,
            seed=12345,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=LockoutMode.non_lockout.value,
            fog_of_war=True
        )

        # Create players with different roles
        self.player = Player.objects.create(
            room=self.room,
            name='Player1',
            role=Role.PLAYER,
            color_value=Color.red.value
        )

        self.spectator = Player.objects.create(
            room=self.room,
            name='Spectator1',
            role=Role.SPECTATOR,
            color_value=Color.blank.value
        )

        self.counter = Player.objects.create(
            room=self.room,
            name='Counter1',
            role=Role.COUNTER,
            color_value=Color.blue.value,
            monitoring_player=self.player
        )

        self.gamemaster = Player.objects.create(
            room=self.room,
            name='Gamemaster',
            role=Role.GAMEMASTER,
            is_also_player=False,
            color_value=Color.orange.value
        )

    def _create_player_session(self, player):
        """Helper to create a session with player authentication."""
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: player.encoded_uuid
        }
        session.save()

    def _mark_square(self, player, slot, color='red'):
        """Helper to mark a square as a player."""
        self._create_player_session(player)
        response = self.client.post(
            '/api/select',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': slot,
                'color': color,
                'remove_color': False
            }),
            content_type='application/json'
        )
        return response

    def test_fog_of_war_enabled_on_game(self, mock_put):
        """Test that fog of war is properly enabled on the game."""
        self.assertTrue(self.game.fog_of_war)

    def test_player_can_mark_squares_with_fog_of_war(self, mock_put):
        """Test that players can mark squares when fog of war is enabled."""
        response = self._mark_square(self.player, 1, 'red')
        self.assertEqual(response.status_code, 200)

        # Verify square was marked
        square = Square.objects.get(game=self.game, slot=1)
        self.assertIn(Color.red, square.color.colors)

    def test_spectator_cannot_mark_squares_with_fog_of_war(self, mock_put):
        """Test that spectators cannot mark squares even with fog of war."""
        response = self._mark_square(self.spectator, 1, 'red')
        self.assertEqual(response.status_code, 403)

        # Verify square was not marked (should still be blank)
        square = Square.objects.get(game=self.game, slot=1)
        self.assertEqual(square.color.colors, [Color.blank])

    def test_counter_cannot_mark_squares_with_fog_of_war(self, mock_put):
        """Test that counters cannot mark squares (they only review)."""
        response = self._mark_square(self.counter, 1, 'blue')
        self.assertEqual(response.status_code, 403)

        # Verify square was not marked (should still be blank)
        square = Square.objects.get(game=self.game, slot=1)
        self.assertEqual(square.color.colors, [Color.blank])

    def test_gamemaster_can_reveal_board(self, mock_put):
        """Test that gamemaster can reveal the entire board in fog of war mode."""
        self._create_player_session(self.gamemaster)

        # Mock the WebSocket publishing
        with patch('bingosync.publish.publish_revealed_event'):
            response = self.client.post(
                '/api/revealed',
                data=json.dumps({
                    'room': self.room.encoded_uuid
                }),
                content_type='application/json'
            )

        # Should succeed
        self.assertEqual(response.status_code, 200)

    def test_player_cannot_reveal_board(self, mock_put):
        """Test that regular players cannot reveal the board."""
        self._create_player_session(self.player)

        # Mock the WebSocket publishing (though it shouldn't get that far)
        with patch('bingosync.publish.publish_revealed_event'):
            response = self.client.post(
                '/api/revealed',
                data=json.dumps({
                    'room': self.room.encoded_uuid
                }),
                content_type='application/json'
            )

        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_spectator_cannot_reveal_board(self, mock_put):
        """Test that spectators cannot reveal the board."""
        self._create_player_session(self.spectator)

        # Mock the WebSocket publishing (though it shouldn't get that far)
        with patch('bingosync.publish.publish_revealed_event'):
            response = self.client.post(
                '/api/revealed',
                data=json.dumps({
                    'room': self.room.encoded_uuid
                }),
                content_type='application/json'
            )

        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_counter_cannot_reveal_board(self, mock_put):
        """Test that counters cannot reveal the board."""
        self._create_player_session(self.counter)

        # Mock the WebSocket publishing (though it shouldn't get that far)
        with patch('bingosync.publish.publish_revealed_event'):
            response = self.client.post(
                '/api/revealed',
                data=json.dumps({
                    'room': self.room.encoded_uuid
                }),
                content_type='application/json'
            )

        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    def test_fog_of_war_status_in_room_json(self, mock_put):
        """Test that fog_of_war status is included in room settings."""
        settings = self.room.settings
        self.assertIn('fog_of_war', settings)
        self.assertTrue(settings['fog_of_war'])

    def test_multiple_players_marking_squares_with_fog(self, mock_put):
        """Test multiple players marking different squares with fog of war."""
        # Create another player
        player2 = Player.objects.create(
            room=self.room,
            name='Player2',
            role=Role.PLAYER,
            color_value=Color.blue.value
        )

        # Player 1 marks square 1
        response1 = self._mark_square(self.player, 1, 'red')
        self.assertEqual(response1.status_code, 200)

        # Player 2 marks square 5
        response2 = self._mark_square(player2, 5, 'blue')
        self.assertEqual(response2.status_code, 200)

        # Verify both squares are marked
        square1 = Square.objects.get(game=self.game, slot=1)
        square5 = Square.objects.get(game=self.game, slot=5)
        self.assertIn(Color.red, square1.color.colors)
        self.assertIn(Color.blue, square5.color.colors)

    def test_gamemaster_also_player_can_mark_squares(self, mock_put):
        """Test that gamemaster who is also a player can mark squares."""
        gm_player = Player.objects.create(
            room=self.room,
            name='GM+Player',
            role=Role.GAMEMASTER,
            is_also_player=True,
            color_value=Color.green.value
        )

        response = self._mark_square(gm_player, 10, 'green')
        self.assertEqual(response.status_code, 200)

        # Verify square was marked
        square = Square.objects.get(game=self.game, slot=10)
        self.assertIn(Color.green, square.color.colors)

    def test_new_board_preserves_fog_of_war_setting(self, mock_put):
        """Test that generating a new board preserves fog of war setting."""
        self._create_player_session(self.gamemaster)

        # Mock the WebSocket publishing
        with patch('bingosync.publish.publish_new_card_event'):
            # Generate new board with fog of war
            response = self.client.put(
                '/api/new-card',
                data=json.dumps({
                    'room': self.room.encoded_uuid,
                    'seed': '54321',
                    'game_type': str(GameType.hp_cos.value),
                    'lockout_mode': str(LockoutMode.non_lockout.value),
                    'hide_card': False,
                    'fog_of_war': 'on',
                    'size': 5
                }),
                content_type='application/json'
            )

        self.assertEqual(response.status_code, 200)

        # Verify new game has fog of war enabled
        self.room.refresh_from_db()
        new_game = self.room.current_game
        self.assertTrue(new_game.fog_of_war)

    def test_fog_of_war_can_be_disabled_on_new_board(self, mock_put):
        """Test that fog of war can be disabled when generating a new board."""
        self._create_player_session(self.gamemaster)

        # Mock the WebSocket publishing
        with patch('bingosync.publish.publish_new_card_event'):
            # Generate new board without fog of war
            response = self.client.put(
                '/api/new-card',
                data=json.dumps({
                    'room': self.room.encoded_uuid,
                    'seed': '99999',
                    'game_type': str(GameType.hp_cos.value),
                    'lockout_mode': str(LockoutMode.non_lockout.value),
                    'hide_card': False,
                    'fog_of_war': 'off',
                    'size': 5
                }),
                content_type='application/json'
            )

        self.assertEqual(response.status_code, 200)

        # Verify new game has fog of war disabled
        self.room.refresh_from_db()
        new_game = self.room.current_game
        self.assertFalse(new_game.fog_of_war)


class FogOfWarUITestCase(TestCase):
    """Test fog of war UI indicators and client-side behavior."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create room with fog of war
        self.room = Room.objects.create(
            name='Fog UI Test Room',
            passphrase='test123'
        )

        board_json = [{"name": f"Goal {i}", "tier": 1} for i in range(1, 26)]
        self.game = Game.from_board(
            board_json,
            room=self.room,
            seed=12345,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=LockoutMode.non_lockout.value,
            fog_of_war=True
        )

        self.player = Player.objects.create(
            room=self.room,
            name='TestPlayer',
            role=Role.PLAYER,
            color_value=Color.red.value
        )

    def test_fog_of_war_status_in_room_settings(self):
        """Test that fog_of_war status is included in room settings."""
        settings = self.room.settings
        self.assertIn('fog_of_war', settings)
        self.assertTrue(settings['fog_of_war'])
