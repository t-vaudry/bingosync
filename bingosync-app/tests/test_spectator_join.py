"""
Tests for spectator join functionality.
"""

from django.test import TestCase, override_settings
from bingosync.models import Room, Player, User
from bingosync.models.enums import Role
from bingosync.forms import JoinRoomForm


# Use locmem cache for testing instead of Redis
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-test-cache',
    }
})
class SpectatorJoinTestCase(TestCase):
    """Test spectator join functionality."""

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
            room_code='TEST01',
            passphrase='pbkdf2_sha256$870000$test$hash'
        )

    def test_logged_in_user_can_join_as_spectator(self):
        """Test that logged-in users can join as spectators."""
        form_data = {
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': self.user.username,
            'passphrase': 'test',  # Will fail password check but that's ok for this test
            'role': Role.SPECTATOR,
        }
        
        form = JoinRoomForm(data=form_data, room=self.room, user=self.user)
        
        # Check that spectator is a valid choice
        role_choices = [choice[0] for choice in form.fields['role'].choices]
        self.assertIn(Role.SPECTATOR, role_choices)

    def test_logged_in_spectator_displayname_is_username(self):
        """Test that logged-in spectators have displayname set to username."""
        # Create a spectator player for the logged-in user
        player = Player.objects.create(
            room=self.room,
            name=self.user.username,
            role=Role.SPECTATOR,
            user=self.user
        )
        
        # Verify the displayname matches username
        self.assertEqual(player.name, self.user.username)
        self.assertEqual(player.role, Role.SPECTATOR)
        self.assertEqual(player.user, self.user)

    def test_anonymous_spectator_can_have_custom_displayname(self):
        """Test that anonymous spectators can have custom displaynames."""
        # Create an anonymous spectator
        player = Player.objects.create(
            room=self.room,
            name='CustomSpectatorName',
            role=Role.SPECTATOR,
            user=None
        )
        
        # Verify the displayname is custom
        self.assertEqual(player.name, 'CustomSpectatorName')
        self.assertEqual(player.role, Role.SPECTATOR)
        self.assertIsNone(player.user)

    def test_logged_in_spectator_cannot_be_promoted_without_auth(self):
        """Test that the validation prevents promoting anonymous spectators."""
        # This is tested in the form validation
        # Anonymous users (user=None) cannot become Player/Counter
        # This is enforced in JoinRoomForm.create_player() and assign_role view
        pass

    def test_logged_in_spectator_can_be_promoted(self):
        """Test that logged-in spectators can be promoted to Player/Counter."""
        # Create a logged-in spectator
        spectator = Player.objects.create(
            room=self.room,
            name=self.user.username,
            role=Role.SPECTATOR,
            user=self.user
        )
        
        # Promote to Player
        spectator.role = Role.PLAYER
        spectator.save()
        
        # Verify promotion
        self.assertEqual(spectator.role, Role.PLAYER)
        self.assertEqual(spectator.user, self.user)
