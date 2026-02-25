"""
Tests for Gamemaster Assignment Options (Task 2.8)

Tests that room creators can choose between:
- Gamemaster-only (cannot mark squares)
- Gamemaster+Player (can mark squares)
"""

from django import test
from bingosync import models, forms
from bingosync.models.enums import Role


class GamemasterAssignmentTestCase(test.TestCase):
    """Test gamemaster assignment options during room creation."""

    def setUp(self):
        """Set up test data."""
        self.base_form_data = {
            "room_name": "Test Room",
            "passphrase": "password",
            "nickname": "TestGM",
            "game_type": str(models.GameType.hp_cos.value),
            "lockout_mode": str(models.LockoutMode.lockout.value),
        }

    def test_gamemaster_plus_player_default(self):
        """Test that default behavior creates GM+Player (can mark squares)."""
        # Create room without gamemaster_only checkbox (default)
        form = forms.RoomForm(self.base_form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        room = form.create_room()
        creator = room.creator
        
        # Verify role is GAMEMASTER
        self.assertEqual(creator.role, Role.GAMEMASTER)
        
        # Verify is_also_player is True (can mark squares)
        self.assertTrue(creator.is_also_player)
        
        # Verify creator can mark squares
        from bingosync.permissions import check_permission
        self.assertTrue(check_permission(creator, 'mark_square'))

    def test_gamemaster_only(self):
        """Test that gamemaster_only checkbox creates GM-only (cannot mark squares)."""
        # Create room with gamemaster_only checkbox
        form_data = self.base_form_data.copy()
        form_data['gamemaster_only'] = True
        
        form = forms.RoomForm(form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        room = form.create_room()
        creator = room.creator
        
        # Verify role is GAMEMASTER
        self.assertEqual(creator.role, Role.GAMEMASTER)
        
        # Verify is_also_player is False (cannot mark squares)
        self.assertFalse(creator.is_also_player)
        
        # Verify creator cannot mark squares
        from bingosync.permissions import check_permission
        self.assertFalse(check_permission(creator, 'mark_square'))

    def test_gamemaster_plus_player_explicit(self):
        """Test that unchecked gamemaster_only creates GM+Player."""
        # Create room with gamemaster_only explicitly set to False
        form_data = self.base_form_data.copy()
        form_data['gamemaster_only'] = False
        
        form = forms.RoomForm(form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        room = form.create_room()
        creator = room.creator
        
        # Verify role is GAMEMASTER
        self.assertEqual(creator.role, Role.GAMEMASTER)
        
        # Verify is_also_player is True (can mark squares)
        self.assertTrue(creator.is_also_player)
        
        # Verify creator can mark squares
        from bingosync.permissions import check_permission
        self.assertTrue(check_permission(creator, 'mark_square'))

    def test_spectator_overrides_gamemaster(self):
        """Test that is_spectator checkbox takes precedence over gamemaster_only."""
        # Create room as spectator (should override gamemaster settings)
        form_data = self.base_form_data.copy()
        form_data['is_spectator'] = True
        form_data['gamemaster_only'] = False  # This should be ignored
        
        form = forms.RoomForm(form_data)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        room = form.create_room()
        creator = room.creator
        
        # Verify role is SPECTATOR (not GAMEMASTER)
        self.assertEqual(creator.role, Role.SPECTATOR)
        
        # Verify is_also_player is False
        self.assertFalse(creator.is_also_player)
        
        # Verify creator cannot mark squares (spectators can't)
        from bingosync.permissions import check_permission
        self.assertFalse(check_permission(creator, 'mark_square'))

    def test_gamemaster_permissions(self):
        """Test that gamemaster has correct permissions regardless of is_also_player."""
        # Test GM-only permissions
        form_data_gm_only = self.base_form_data.copy()
        form_data_gm_only['gamemaster_only'] = True
        form_gm_only = forms.RoomForm(form_data_gm_only)
        self.assertTrue(form_gm_only.is_valid())
        room_gm_only = form_gm_only.create_room()
        gm_only = room_gm_only.creator
        
        # Test GM+Player permissions
        form_data_gm_player = self.base_form_data.copy()
        form_data_gm_player['gamemaster_only'] = False
        form_gm_player = forms.RoomForm(form_data_gm_player)
        self.assertTrue(form_gm_player.is_valid())
        room_gm_player = form_gm_player.create_room()
        gm_player = room_gm_player.creator
        
        from bingosync.permissions import check_permission
        
        # Both should have GM permissions
        for gm in [gm_only, gm_player]:
            self.assertTrue(check_permission(gm, 'generate_board'))
            self.assertTrue(check_permission(gm, 'reveal_fog'))
            self.assertTrue(check_permission(gm, 'assign_roles'))
            self.assertTrue(check_permission(gm, 'remove_players'))
            self.assertTrue(check_permission(gm, 'delete_room'))
        
        # Only GM+Player should be able to mark squares
        self.assertFalse(check_permission(gm_only, 'mark_square'))
        self.assertTrue(check_permission(gm_player, 'mark_square'))

    def test_player_json_includes_role_info(self):
        """Test that player.to_json() includes role and is_also_player."""
        # Create GM+Player
        form_data = self.base_form_data.copy()
        form_data['gamemaster_only'] = False
        form = forms.RoomForm(form_data)
        self.assertTrue(form.is_valid())
        room = form.create_room()
        creator = room.creator
        
        # Get JSON representation
        player_json = creator.to_json()
        
        # Verify role and is_also_player are in JSON
        self.assertIn('role', player_json)
        self.assertIn('is_also_player', player_json)
        self.assertEqual(player_json['role'], Role.GAMEMASTER)
        self.assertTrue(player_json['is_also_player'])
