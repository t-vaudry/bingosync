"""
Tests for role-based permissions system.
"""

from django.test import TestCase
from bingosync.models import Room, Player, User
from bingosync.models.enums import Role
from bingosync.permissions import check_permission


class RolePermissionsTestCase(TestCase):
    """Test role-based permission checking."""
    
    def setUp(self):
        """Set up test data."""
        # Create a test user and room
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.room = Room.objects.create(
            name='Test Room',
            passphrase='test123'
        )
    
    def test_gamemaster_permissions(self):
        """Test Gamemaster role permissions."""
        # Create Gamemaster player (not also a player)
        gm = Player.objects.create(
            room=self.room,
            name='Gamemaster',
            role=Role.GAMEMASTER,
            is_also_player=False
        )
        
        # Gamemaster can generate board
        self.assertTrue(check_permission(gm, 'generate_board'))
        
        # Gamemaster can reveal fog
        self.assertTrue(check_permission(gm, 'reveal_fog'))
        
        # Gamemaster can assign roles
        self.assertTrue(check_permission(gm, 'assign_roles'))
        
        # Gamemaster can remove players
        self.assertTrue(check_permission(gm, 'remove_players'))
        
        # Gamemaster can delete room
        self.assertTrue(check_permission(gm, 'delete_room'))
        
        # Gamemaster can view board
        self.assertTrue(check_permission(gm, 'view_board'))
        
        # Gamemaster can chat
        self.assertTrue(check_permission(gm, 'chat'))
        
        # Gamemaster CANNOT mark squares (not also a player)
        self.assertFalse(check_permission(gm, 'mark_square'))
    
    def test_gamemaster_also_player_permissions(self):
        """Test Gamemaster who is also a player can mark squares."""
        # Create Gamemaster player who is also a player
        gm_player = Player.objects.create(
            room=self.room,
            name='GM+Player',
            role=Role.GAMEMASTER,
            is_also_player=True
        )
        
        # Gamemaster+Player CAN mark squares
        self.assertTrue(check_permission(gm_player, 'mark_square'))
        
        # Still has all other GM permissions
        self.assertTrue(check_permission(gm_player, 'generate_board'))
        self.assertTrue(check_permission(gm_player, 'reveal_fog'))
    
    def test_player_permissions(self):
        """Test Player role permissions."""
        player = Player.objects.create(
            room=self.room,
            name='Player',
            role=Role.PLAYER
        )
        
        # Player can mark squares
        self.assertTrue(check_permission(player, 'mark_square'))
        
        # Player can view board
        self.assertTrue(check_permission(player, 'view_board'))
        
        # Player can chat
        self.assertTrue(check_permission(player, 'chat'))
        
        # Player CANNOT generate board
        self.assertFalse(check_permission(player, 'generate_board'))
        
        # Player CANNOT reveal fog
        self.assertFalse(check_permission(player, 'reveal_fog'))
        
        # Player CANNOT assign roles
        self.assertFalse(check_permission(player, 'assign_roles'))
        
        # Player CANNOT remove players
        self.assertFalse(check_permission(player, 'remove_players'))
        
        # Player CANNOT delete room
        self.assertFalse(check_permission(player, 'delete_room'))
    
    def test_counter_permissions(self):
        """Test Counter role permissions."""
        counter = Player.objects.create(
            room=self.room,
            name='Counter',
            role=Role.COUNTER
        )
        
        # Counter can view board
        self.assertTrue(check_permission(counter, 'view_board'))
        
        # Counter can review claims
        self.assertTrue(check_permission(counter, 'review_claims'))
        
        # Counter can chat
        self.assertTrue(check_permission(counter, 'chat'))
        
        # Counter CANNOT mark squares
        self.assertFalse(check_permission(counter, 'mark_square'))
        
        # Counter CANNOT generate board
        self.assertFalse(check_permission(counter, 'generate_board'))
        
        # Counter CANNOT reveal fog
        self.assertFalse(check_permission(counter, 'reveal_fog'))
        
        # Counter CANNOT assign roles
        self.assertFalse(check_permission(counter, 'assign_roles'))
    
    def test_spectator_permissions(self):
        """Test Spectator role permissions."""
        spectator = Player.objects.create(
            room=self.room,
            name='Spectator',
            role=Role.SPECTATOR,
            is_spectator=True
        )
        
        # Spectator can view board
        self.assertTrue(check_permission(spectator, 'view_board'))
        
        # Spectator can chat
        self.assertTrue(check_permission(spectator, 'chat'))
        
        # Spectator CANNOT mark squares
        self.assertFalse(check_permission(spectator, 'mark_square'))
        
        # Spectator CANNOT generate board
        self.assertFalse(check_permission(spectator, 'generate_board'))
        
        # Spectator CANNOT reveal fog
        self.assertFalse(check_permission(spectator, 'reveal_fog'))
        
        # Spectator CANNOT assign roles
        self.assertFalse(check_permission(spectator, 'assign_roles'))
        
        # Spectator CANNOT review claims
        self.assertFalse(check_permission(spectator, 'review_claims'))
    
    def test_invalid_player(self):
        """Test permission check with invalid player."""
        # None player should return False
        self.assertFalse(check_permission(None, 'mark_square'))
        
        # Player without role attribute should return False
        class FakePlayer:
            pass
        
        fake_player = FakePlayer()
        self.assertFalse(check_permission(fake_player, 'mark_square'))
    
    def test_unknown_action(self):
        """Test permission check with unknown action."""
        player = Player.objects.create(
            room=self.room,
            name='Player',
            role=Role.PLAYER
        )
        
        # Unknown action should return False
        self.assertFalse(check_permission(player, 'unknown_action'))
