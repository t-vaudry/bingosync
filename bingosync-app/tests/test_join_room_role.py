"""
Tests for join room role assignment.
"""
from django.test import TestCase
from django.contrib.auth import hashers, get_user_model
from bingosync.models.rooms import Room, Game
from bingosync.models.enums import Role
from bingosync.models.game_type import GameType
from bingosync.forms import JoinRoomForm

User = get_user_model()


class JoinRoomRoleTestCase(TestCase):
    """Test that joining a room correctly sets the role."""

    def setUp(self):
        """Set up test data."""
        # Create a test user and room creator
        from django.contrib.auth import get_user_model
        User = get_user_model()
        creator_user = User.objects.create_user(
            username='creator',
            email='creator@test.com',
            password='testpass123'
        )
        
        # Create a test room
        encrypted_passphrase = hashers.make_password('testpass')
        self.room = Room.objects.create(
            name='Test Room',
            passphrase=encrypted_passphrase,
            hide_card=False,
            active=True  # Set active to allow spectators to join
        )
        
        # Create a game to make the room active
        self.game = Game.objects.create(
            room=self.room,
            seed=12345,
            size=5,
            game_type_value=GameType.hp_cos.value
        )
        
        # Create a creator player to keep room active
        from bingosync.models.rooms import Player
        from bingosync.models.colors import Color
        self.creator = Player.objects.create(
            room=self.room,
            user=creator_user,
            name='Creator',
            role=Role.GAMEMASTER,
            color_value=Color.orange.value
        )

    def test_join_as_player(self):
        """Test joining as a player sets role to PLAYER."""
        # Create a user for authentication
        user = User.objects.create_user(
            username='testplayer',
            email='player@test.com',
            password='testpass123'
        )
        
        form_data = {
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'TestPlayer',
            'passphrase': 'testpass',
            'role': Role.PLAYER,
        }
        form = JoinRoomForm(data=form_data, user=user)
        self.assertTrue(form.is_valid(), form.errors)

        player = form.create_player(user=user)

        self.assertEqual(player.role, Role.PLAYER)
        self.assertFalse(player.is_spectator)  # Property derived from role

    def test_join_as_spectator(self):
        """Test joining as a spectator sets role to SPECTATOR."""
        form_data = {
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'TestSpectator',
            'passphrase': 'testpass',
            'role': Role.SPECTATOR,
        }
        form = JoinRoomForm(data=form_data, user=None)
        self.assertTrue(form.is_valid(), form.errors)

        player = form.create_player(user=None)

        self.assertEqual(player.role, Role.SPECTATOR)
        self.assertTrue(player.is_spectator)  # Property derived from role

    def test_join_as_counter(self):
        """Test joining as a counter sets role to COUNTER."""
        # Create a user for authentication
        user = User.objects.create_user(
            username='testcounter',
            email='counter@test.com',
            password='testpass123'
        )
        
        form_data = {
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'TestCounter',
            'passphrase': 'testpass',
            'role': Role.COUNTER,
        }
        form = JoinRoomForm(data=form_data, user=user)
        self.assertTrue(form.is_valid(), form.errors)

        player = form.create_player(user=user)

        self.assertEqual(player.role, Role.COUNTER)
        self.assertFalse(player.is_spectator)  # Property derived from role

    def test_role_spectator_consistency(self):
        """Test that is_spectator property is consistent with role."""
        # Join as spectator (no authentication required)
        form_data = {
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'Spectator1',
            'passphrase': 'testpass',
            'role': Role.SPECTATOR,
        }
        form = JoinRoomForm(data=form_data, user=None)
        self.assertTrue(form.is_valid())
        spectator = form.create_player(user=None)

        # Verify consistency
        self.assertEqual(spectator.role, Role.SPECTATOR)
        self.assertTrue(spectator.is_spectator)  # Property derived from role

        # Join as player (requires authentication)
        user = User.objects.create_user(
            username='testplayer2',
            email='player2@test.com',
            password='testpass123'
        )
        form_data['player_name'] = 'Player1'
        form_data['role'] = Role.PLAYER
        form = JoinRoomForm(data=form_data, user=user)
        self.assertTrue(form.is_valid())
        player = form.create_player(user=user)

        # Verify consistency
        self.assertEqual(player.role, Role.PLAYER)
        self.assertFalse(player.is_spectator)  # Property derived from role
