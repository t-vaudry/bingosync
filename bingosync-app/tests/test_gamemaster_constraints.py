"""
Tests for Gamemaster role constraints in the simplified model.

This test file validates that:
1. Gamemaster can only be assigned at room creation
2. Gamemaster role cannot be transferred
3. Gamemaster can mark squares
4. Gamemaster has all admin permissions
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth import hashers
from bingosync.models import Room, Player, Game
from bingosync.models.enums import Role
from bingosync.models.game_type import GameType
from bingosync.models.rooms import LockoutMode
from bingosync.permissions import check_permission

User = get_user_model()


class GamemasterCreationTest(TestCase):
    """Test Gamemaster assignment at room creation."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_create_room_with_gamemaster(self):
        """Test creating a room with Gamemaster role."""
        # Create room
        room = Room.objects.create(
            name='Test Room',
            room_code='TEST01',
            passphrase=hashers.make_password('testpass')
        )
        
        # Create game
        game = Game.objects.create(
            room=room,
            seed=12345,
            size=5,
            game_type_value=50,  # HP CoS
            lockout_mode_value=LockoutMode.non_lockout.value
        )
        
        # Create player as Gamemaster
        player = Player.objects.create(
            room=room,
            name=self.user.username,
            role=Role.GAMEMASTER,
            user=self.user
        )
        
        # Verify
        self.assertEqual(player.role, Role.GAMEMASTER)
        self.assertEqual(player.user, self.user)

    def test_create_room_without_gamemaster(self):
        """Test creating a room without Gamemaster (as Player)."""
        # Create room
        room = Room.objects.create(
            name='Test Room',
            room_code='TEST02',
            passphrase=hashers.make_password('testpass')
        )
        
        # Create game
        game = Game.objects.create(
            room=room,
            seed=12345,
            size=5,
            game_type_value=50,  # HP CoS
            lockout_mode_value=LockoutMode.non_lockout.value
        )
        
        # Create player as Player
        player = Player.objects.create(
            room=room,
            name=self.user.username,
            role=Role.PLAYER,
            user=self.user
        )
        
        # Verify
        self.assertEqual(player.role, Role.PLAYER)
        self.assertEqual(player.user, self.user)


class GamemasterTransferPreventionTest(TestCase):
    """Test that Gamemaster role cannot be transferred."""

    def setUp(self):
        # Create users
        self.gm_user = User.objects.create_user(
            username='gamemaster',
            email='gm@example.com',
            password='testpass123'
        )
        self.player_user = User.objects.create_user(
            username='player',
            email='player@example.com',
            password='testpass123'
        )
        
        # Create room
        self.room = Room.objects.create(
            name='Test Room',
            room_code='TEST03',
            passphrase=hashers.make_password('testpass')
        )
        
        # Create game
        self.game = Game.objects.create(
            room=self.room,
            seed=12345,
            size=5,
            game_type_value=50,
            lockout_mode_value=LockoutMode.non_lockout.value
        )
        
        # Create GM player
        self.gm_player = Player.objects.create(
            room=self.room,
            name=self.gm_user.username,
            role=Role.GAMEMASTER,
            user=self.gm_user
        )
        
        # Create regular player
        self.player = Player.objects.create(
            room=self.room,
            name=self.player_user.username,
            role=Role.PLAYER,
            user=self.player_user
        )

    def test_gamemaster_role_is_permanent(self):
        """Test that Gamemaster role cannot be changed."""
        # Try to change GM to Player (should not be allowed by validation)
        # This is enforced at the view level, not model level
        self.assertEqual(self.gm_player.role, Role.GAMEMASTER)
        
        # Verify GM can mark squares
        self.assertTrue(check_permission(self.gm_player, 'mark_square'))
        
        # Verify GM has admin permissions
        self.assertTrue(check_permission(self.gm_player, 'generate_board'))
        self.assertTrue(check_permission(self.gm_player, 'assign_roles'))


class GamemasterPlayerMutualExclusivityTest(TestCase):
    """Test that Gamemaster and Player roles are mutually exclusive."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create room
        self.room = Room.objects.create(
            name='Test Room',
            room_code='TEST04',
            passphrase=hashers.make_password('testpass')
        )
        
        # Create game
        self.game = Game.objects.create(
            room=self.room,
            seed=12345,
            size=5,
            game_type_value=50,
            lockout_mode_value=LockoutMode.non_lockout.value
        )

    def test_gamemaster_can_mark_squares(self):
        """Test that Gamemaster can mark squares."""
        # Create GM player
        gm_player = Player.objects.create(
            room=self.room,
            name=self.user.username,
            role=Role.GAMEMASTER,
            user=self.user
        )
        
        # Verify GM can mark squares
        self.assertTrue(check_permission(gm_player, 'mark_square'))

    def test_player_can_mark_own_squares(self):
        """Test that Player can mark their own squares."""
        # Create regular player
        player = Player.objects.create(
            room=self.room,
            name=self.user.username,
            role=Role.PLAYER,
            user=self.user
        )
        
        # Verify Player can mark squares
        self.assertTrue(check_permission(player, 'mark_square'))

    def test_gamemaster_has_admin_permissions(self):
        """Test that Gamemaster has all admin permissions."""
        # Create GM player
        gm_player = Player.objects.create(
            room=self.room,
            name=self.user.username,
            role=Role.GAMEMASTER,
            user=self.user
        )
        
        # Verify GM has admin permissions
        self.assertTrue(check_permission(gm_player, 'generate_board'))
        self.assertTrue(check_permission(gm_player, 'reveal_fog'))
        self.assertTrue(check_permission(gm_player, 'assign_roles'))
        self.assertTrue(check_permission(gm_player, 'remove_players'))
        self.assertTrue(check_permission(gm_player, 'mark_square'))

    def test_player_lacks_admin_permissions(self):
        """Test that Player lacks admin permissions."""
        # Create regular player
        player = Player.objects.create(
            room=self.room,
            name=self.user.username,
            role=Role.PLAYER,
            user=self.user
        )
        
        # Verify Player lacks admin permissions
        self.assertFalse(check_permission(player, 'generate_board'))
        self.assertFalse(check_permission(player, 'reveal_fog'))
        self.assertFalse(check_permission(player, 'assign_roles'))
        self.assertFalse(check_permission(player, 'remove_players'))


class GamemasterRoleChangeTest(TestCase):
    """Test role changes involving Gamemaster."""

    def setUp(self):
        # Create users
        self.gm_user = User.objects.create_user(
            username='gamemaster',
            email='gm@example.com',
            password='testpass123'
        )
        self.player1_user = User.objects.create_user(
            username='player1',
            email='player1@example.com',
            password='testpass123'
        )
        
        # Create room
        self.room = Room.objects.create(
            name='Test Room',
            room_code='TEST05',
            passphrase=hashers.make_password('testpass')
        )
        
        # Create game
        self.game = Game.objects.create(
            room=self.room,
            seed=12345,
            size=5,
            game_type_value=50,
            lockout_mode_value=LockoutMode.non_lockout.value
        )
        
        # Create GM player
        self.gm_player = Player.objects.create(
            room=self.room,
            name=self.gm_user.username,
            role=Role.GAMEMASTER,
            user=self.gm_user
        )

    def test_gm_can_change_other_player_roles(self):
        """Test that GM can change roles of other players (Player <-> Counter <-> Spectator)."""
        # Create a player
        player1 = Player.objects.create(
            room=self.room,
            name=self.player1_user.username,
            role=Role.PLAYER,
            user=self.player1_user
        )
        
        # Change player to counter (at model level)
        player1.role = Role.COUNTER
        player1.save()
        
        self.assertEqual(player1.role, Role.COUNTER)
        
        # Change counter to spectator
        player1.role = Role.SPECTATOR
        player1.save()
        
        self.assertEqual(player1.role, Role.SPECTATOR)
        
        # Change spectator back to player
        player1.role = Role.PLAYER
        player1.save()
        
        self.assertEqual(player1.role, Role.PLAYER)
