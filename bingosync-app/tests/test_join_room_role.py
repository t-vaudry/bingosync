"""
Tests for join room role assignment.
"""
from django.test import TestCase
from django.contrib.auth import hashers
from bingosync.models.rooms import Room
from bingosync.models.enums import Role
from bingosync.forms import JoinRoomForm


class JoinRoomRoleTestCase(TestCase):
    """Test that joining a room correctly sets the role."""

    def setUp(self):
        """Set up test data."""
        # Create a test room
        encrypted_passphrase = hashers.make_password('testpass')
        self.room = Room.objects.create(
            name='Test Room',
            passphrase=encrypted_passphrase,
            hide_card=False
        )

    def test_join_as_player(self):
        """Test joining as a player sets role to PLAYER."""
        form_data = {
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'TestPlayer',
            'passphrase': 'testpass',
            'role': Role.PLAYER,
        }
        form = JoinRoomForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

        player = form.create_player()

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
        form = JoinRoomForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

        player = form.create_player()

        self.assertEqual(player.role, Role.SPECTATOR)
        self.assertTrue(player.is_spectator)  # Property derived from role

    def test_join_as_counter(self):
        """Test joining as a counter sets role to COUNTER."""
        form_data = {
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'TestCounter',
            'passphrase': 'testpass',
            'role': Role.COUNTER,
        }
        form = JoinRoomForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

        player = form.create_player()

        self.assertEqual(player.role, Role.COUNTER)
        self.assertFalse(player.is_spectator)  # Property derived from role

    def test_role_spectator_consistency(self):
        """Test that is_spectator property is consistent with role."""
        # Join as spectator
        form_data = {
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'Spectator1',
            'passphrase': 'testpass',
            'role': Role.SPECTATOR,
        }
        form = JoinRoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        spectator = form.create_player()

        # Verify consistency
        self.assertEqual(spectator.role, Role.SPECTATOR)
        self.assertTrue(spectator.is_spectator)  # Property derived from role

        # Join as player
        form_data['player_name'] = 'Player1'
        form_data['role'] = Role.PLAYER
        form = JoinRoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        player = form.create_player()

        # Verify consistency
        self.assertEqual(player.role, Role.PLAYER)
        self.assertFalse(player.is_spectator)  # Property derived from role
