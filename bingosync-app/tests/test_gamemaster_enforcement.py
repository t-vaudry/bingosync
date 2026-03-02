"""
Tests for gamemaster enforcement rules:
- Exactly one gamemaster at all times
- GM cannot demote themselves to Player/Counter
- GM transfer makes old GM a spectator
- Auto-promote on GM disconnect
"""

from django.test import TestCase, Client, override_settings
from unittest.mock import patch
from bingosync.models import Room, Player, User
from bingosync.models.enums import Role
from bingosync.models.colors import Color
import json


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-test-cache',
        }
    },
    RATELIMIT_ENABLE=False
)
class GamemasterEnforcementTestCase(TestCase):
    """Test gamemaster enforcement rules."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        
        # Create users
        self.gm_user = User.objects.create_user(
            username='gmuser',
            email='gm@example.com',
            password='testpass123'
        )
        self.player1_user = User.objects.create_user(
            username='player1',
            email='player1@example.com',
            password='testpass123'
        )
        self.player2_user = User.objects.create_user(
            username='player2',
            email='player2@example.com',
            password='testpass123'
        )
        
        # Create room
        self.room = Room.objects.create(
            name='Test Room',
            room_code='TEST01',
            passphrase='pbkdf2_sha256$870000$test$hash'
        )
        
        # Create GM+Player
        self.gm_player = Player.objects.create(
            room=self.room,
            name='Gamemaster',
            role=Role.GAMEMASTER,
            is_also_player=True,
            user=self.gm_user,
            color_value=Color.orange.value
        )
        
        # Create regular players
        self.player1 = Player.objects.create(
            room=self.room,
            name='Player1',
            role=Role.PLAYER,
            user=self.player1_user,
            color_value=Color.blue.value
        )
        
        self.player2 = Player.objects.create(
            room=self.room,
            name='Player2',
            role=Role.PLAYER,
            user=self.player2_user,
            color_value=Color.green.value
        )

    @patch('bingosync.views.publish_role_change_event')
    def test_gm_cannot_demote_to_player(self, mock_publish):
        """Test that GM cannot change themselves to Player."""
        self.client.force_login(self.gm_user)
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()
        
        response = self.client.post(
            '/api/assign-role',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': self.gm_player.encoded_uuid,
                'new_role': Role.PLAYER
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'cannot change to Player', response.content)
        
        # Verify role unchanged
        self.gm_player.refresh_from_db()
        self.assertEqual(self.gm_player.role, Role.GAMEMASTER)

    @patch('bingosync.views.publish_role_change_event')
    def test_gm_can_toggle_player_mode(self, mock_publish):
        """Test that GM can toggle between GM and GM+Player."""
        self.client.force_login(self.gm_user)
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()
        
        # Initially GM+Player
        self.assertTrue(self.gm_player.is_also_player)
        
        # Toggle to GM-only
        response = self.client.post(
            '/api/assign-role',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': self.gm_player.encoded_uuid,
                'new_role': Role.GAMEMASTER
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        self.gm_player.refresh_from_db()
        self.assertFalse(self.gm_player.is_also_player)

    @patch('bingosync.views.publish_role_change_event')
    def test_gm_transfer_makes_old_gm_spectator(self, mock_publish):
        """Test that transferring GM makes old GM a spectator."""
        self.client.force_login(self.gm_user)
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()
        
        # Transfer GM to player1
        response = self.client.post(
            '/api/assign-role',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': self.player1.encoded_uuid,
                'new_role': Role.GAMEMASTER
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Old GM is now spectator
        self.gm_player.refresh_from_db()
        self.assertEqual(self.gm_player.role, Role.SPECTATOR)
        self.assertFalse(self.gm_player.is_also_player)
        
        # New GM is GM+Player
        self.player1.refresh_from_db()
        self.assertEqual(self.player1.role, Role.GAMEMASTER)
        self.assertTrue(self.player1.is_also_player)

    @patch('bingosync.views.publish_role_change_event')
    def test_gm_to_spectator_auto_transfers(self, mock_publish):
        """Test that GM changing to spectator auto-transfers to next player."""
        self.client.force_login(self.gm_user)
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()
        
        # GM changes to spectator
        response = self.client.post(
            '/api/assign-role',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': self.gm_player.encoded_uuid,
                'new_role': Role.SPECTATOR
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Old GM is spectator
        self.gm_player.refresh_from_db()
        self.assertEqual(self.gm_player.role, Role.SPECTATOR)
        
        # Next player became GM
        self.player1.refresh_from_db()
        self.assertEqual(self.player1.role, Role.GAMEMASTER)
        self.assertTrue(self.player1.is_also_player)
