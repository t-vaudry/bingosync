"""
Tests for role change functionality (Task 2.9).
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.events import RoleChangeEvent
from bingosync.models.enums import Role
from bingosync.models.game_type import GameType
from bingosync.models.colors import Color
import json

User = get_user_model()


class RoleChangeTestCase(TestCase):
    """Test role change functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create users
        self.gm_user = User.objects.create_user(
            username='gamemaster',
            email='gm@test.com',
            password='testpass123'
        )
        self.player_user = User.objects.create_user(
            username='player1',
            email='player1@test.com',
            password='testpass123'
        )
        
        # Create room
        self.room = Room.objects.create(
            name='Test Room',
            passphrase='test123'
        )
        
        # Create game
        self.game = Game.objects.create(
            room=self.room,
            seed=12345,
            size=5,
            game_type_value=GameType.hp_cos.value
        )
        
        # Create gamemaster player
        self.gm_player = Player.objects.create(
            room=self.room,
            name='Gamemaster',
            role=Role.GAMEMASTER,
            is_also_player=True,
            color_value=Color.orange.value
        )
        
        # Create regular player
        self.regular_player = Player.objects.create(
            room=self.room,
            name='Player1',
            role=Role.PLAYER,
            color_value=Color.blue.value
        )
        
        self.client = Client()
    
    def test_gamemaster_can_change_role(self):
        """Test that Gamemaster can change another player's role."""
        # Login as gamemaster
        self.client.force_login(self.gm_user)
        
        # Store session player
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()
        
        # Change regular player's role to Counter
        response = self.client.post(
            '/api/assign-role',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': self.regular_player.encoded_uuid,
                'new_role': Role.COUNTER
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify role was changed
        self.regular_player.refresh_from_db()
        self.assertEqual(self.regular_player.role, Role.COUNTER)
        
        # Verify RoleChangeEvent was created
        role_change_events = RoleChangeEvent.objects.filter(
            player=self.gm_player,
            target_player=self.regular_player
        )
        self.assertEqual(role_change_events.count(), 1)
        
        event = role_change_events.first()
        self.assertEqual(event.old_role, Role.PLAYER)
        self.assertEqual(event.new_role, Role.COUNTER)
    
    def test_regular_player_cannot_change_role(self):
        """Test that regular Player cannot change roles."""
        # Login as regular player
        self.client.force_login(self.player_user)
        
        # Store session player
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.regular_player.encoded_uuid
        }
        session.save()
        
        # Try to change gamemaster's role
        response = self.client.post(
            '/api/assign-role',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': self.gm_player.encoded_uuid,
                'new_role': Role.SPECTATOR
            }),
            content_type='application/json'
        )
        
        # Should be forbidden
        self.assertEqual(response.status_code, 403)
        
        # Verify role was NOT changed
        self.gm_player.refresh_from_db()
        self.assertEqual(self.gm_player.role, Role.GAMEMASTER)
    
    def test_role_change_to_gamemaster_sets_is_also_player(self):
        """Test that changing to Gamemaster sets is_also_player to True."""
        # Login as gamemaster
        self.client.force_login(self.gm_user)
        
        # Store session player
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()
        
        # Change regular player's role to Gamemaster
        response = self.client.post(
            '/api/assign-role',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': self.regular_player.encoded_uuid,
                'new_role': Role.GAMEMASTER
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify is_also_player was set
        self.regular_player.refresh_from_db()
        self.assertEqual(self.regular_player.role, Role.GAMEMASTER)
        self.assertTrue(self.regular_player.is_also_player)
    
    def test_role_change_from_gamemaster_clears_is_also_player(self):
        """Test that changing from Gamemaster clears is_also_player."""
        # Login as gamemaster
        self.client.force_login(self.gm_user)
        
        # Store session player
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()
        
        # Change gamemaster's role to Player
        response = self.client.post(
            '/api/assign-role',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': self.gm_player.encoded_uuid,
                'new_role': Role.PLAYER
            }),
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify is_also_player was cleared
        self.gm_player.refresh_from_db()
        self.assertEqual(self.gm_player.role, Role.PLAYER)
        self.assertFalse(self.gm_player.is_also_player)
    
    def test_role_change_event_to_json(self):
        """Test RoleChangeEvent.to_json() format."""
        # Create a role change event
        event = RoleChangeEvent.objects.create(
            player=self.gm_player,
            player_color_value=self.gm_player.color.value,
            target_player=self.regular_player,
            old_role=Role.PLAYER,
            new_role=Role.COUNTER
        )
        
        # Get JSON representation
        json_data = event.to_json()
        
        # Verify structure
        self.assertEqual(json_data['type'], 'role_change')
        self.assertEqual(json_data['player']['uuid'], self.gm_player.encoded_uuid)
        self.assertEqual(json_data['target_player']['uuid'], self.regular_player.encoded_uuid)
        self.assertEqual(json_data['old_role'], Role.PLAYER)
        self.assertEqual(json_data['new_role'], Role.COUNTER)
        self.assertIn('timestamp', json_data)
    
    def test_invalid_role_rejected(self):
        """Test that invalid role values are rejected."""
        # Login as gamemaster
        self.client.force_login(self.gm_user)
        
        # Store session player
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()
        
        # Try to set invalid role
        response = self.client.post(
            '/api/assign-role',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': self.regular_player.encoded_uuid,
                'new_role': 'invalid_role'
            }),
            content_type='application/json'
        )
        
        # Should be bad request
        self.assertEqual(response.status_code, 400)
        
        # Verify role was NOT changed
        self.regular_player.refresh_from_db()
        self.assertEqual(self.regular_player.role, Role.PLAYER)
