"""
Tests for Gamemaster Assignment Options (Task 2.8 / 3.15)

Tests that room creators can choose between:
- Regular Player (default)
- Gamemaster (via assign_gamemaster checkbox)

In the simplified model:
- Gamemaster is optional
- Gamemaster can mark squares (no is_also_player field)
- Gamemaster role is permanent and cannot be transferred
"""

from django import test
from django.test import override_settings
from django.contrib.auth import get_user_model
from bingosync import models, forms
from bingosync.models.enums import Role
from bingosync.models.rooms import Player

User = get_user_model()


# Use locmem cache for testing instead of Redis
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-test-cache-gm-assignment',
    }
})
class GamemasterAssignmentTestCase(test.TestCase):
    """Test gamemaster assignment options during room creation."""

    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.base_form_data = {
            "room_name": "Test Room",
            "passphrase": "password",
            "nickname": "TestUser",
            "game_type": str(models.GameType.hp_cos.value),
            "lockout_mode": str(models.LockoutMode.lockout.value),
        }

    def test_player_default(self):
        """Test that default behavior creates regular Player."""
        # Create room without assign_gamemaster checkbox (default)
        form = forms.RoomForm(self.base_form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        room = form.create_room(user=self.user)
        creator = room.creator

        # Verify role is PLAYER (not GAMEMASTER)
        self.assertEqual(creator.role, Role.PLAYER)

        # Verify creator can mark squares
        from bingosync.permissions import check_permission
        self.assertTrue(check_permission(creator, 'mark_square'))

    def test_gamemaster_assignment(self):
        """Test that assign_gamemaster checkbox creates Gamemaster."""
        # Create room with assign_gamemaster checkbox
        form_data = self.base_form_data.copy()
        form_data['assign_gamemaster'] = True

        form = forms.RoomForm(form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        room = form.create_room(user=self.user)
        creator = room.creator

        # Verify role is GAMEMASTER
        self.assertEqual(creator.role, Role.GAMEMASTER)

        # Verify creator CAN mark squares (simplified model)
        from bingosync.permissions import check_permission
        self.assertTrue(check_permission(creator, 'mark_square'))

    def test_player_explicit(self):
        """Test that unchecked assign_gamemaster creates Player."""
        # Create room with assign_gamemaster explicitly set to False
        form_data = self.base_form_data.copy()
        form_data['assign_gamemaster'] = False

        form = forms.RoomForm(form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")

        room = form.create_room(user=self.user)
        creator = room.creator

        # Verify role is PLAYER
        self.assertEqual(creator.role, Role.PLAYER)

        # Verify creator can mark squares
        from bingosync.permissions import check_permission
        self.assertTrue(check_permission(creator, 'mark_square'))

    def test_spectator_overrides_gamemaster(self):
        """Test that spectator role is properly set when creating a room as spectator."""
        # Note: In the current implementation, room creators are always Player or Gamemaster
        # This test verifies that the role system works correctly
        # If we want to allow spectator room creation in the future, this test documents that behavior
        
        # For now, skip this test as room creators must be Player or Gamemaster
        self.skipTest("Room creators must be Player or Gamemaster in current implementation")

    def test_gamemaster_permissions(self):
        """Test that gamemaster has correct permissions."""
        # Create GM
        form_data_gm = self.base_form_data.copy()
        form_data_gm['assign_gamemaster'] = True
        form_gm = forms.RoomForm(form_data_gm)
        self.assertTrue(form_gm.is_valid())
        room_gm = form_gm.create_room(user=self.user)
        gm = room_gm.creator

        from bingosync.permissions import check_permission

        # GM should have all admin permissions
        self.assertTrue(check_permission(gm, 'generate_board'))
        self.assertTrue(check_permission(gm, 'reveal_fog'))
        self.assertTrue(check_permission(gm, 'assign_roles'))
        self.assertTrue(check_permission(gm, 'remove_players'))
        self.assertTrue(check_permission(gm, 'delete_room'))
        
        # GM CAN mark squares in simplified model
        self.assertTrue(check_permission(gm, 'mark_square'))

    def test_player_json_includes_role_info(self):
        """Test that player.to_json() includes role (no is_also_player in simplified model)."""
        # Create Player
        form_data = self.base_form_data.copy()
        form_data['assign_gamemaster'] = False
        form = forms.RoomForm(form_data)
        self.assertTrue(form.is_valid())
        room = form.create_room(user=self.user)
        creator = room.creator

        # Get JSON representation
        player_json = creator.to_json()

        # Verify role and is_logged_in are in JSON (no is_also_player in simplified model)
        self.assertIn('role', player_json)
        self.assertIn('is_logged_in', player_json)
        self.assertEqual(player_json['role'], Role.PLAYER)
        self.assertTrue(player_json['is_logged_in'])  # Creator is logged in

    def test_player_json_includes_is_logged_in(self):
        """Test that player.to_json() includes is_logged_in field."""
        # Create room
        form_data = self.base_form_data.copy()
        form = forms.RoomForm(form_data)
        self.assertTrue(form.is_valid())
        room = form.create_room(user=self.user)
        
        # Create anonymous spectator
        anon_spectator = Player.objects.create(
            room=room,
            name='Anonymous',
            role=Role.SPECTATOR,
            user=None
        )
        
        # Check logged-in player
        creator_json = room.creator.to_json()
        self.assertIn('is_logged_in', creator_json)
        self.assertTrue(creator_json['is_logged_in'])
        
        # Check anonymous player
        anon_json = anon_spectator.to_json()
        self.assertIn('is_logged_in', anon_json)
        self.assertFalse(anon_json['is_logged_in'])
