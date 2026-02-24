"""
Tests for one room per user enforcement (Task 2.5).
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from bingosync.models.user import User
from bingosync.models.rooms import Room, Player
from bingosync.forms import RoomForm, JoinRoomForm


class OneRoomPerUserTests(TestCase):
    """Test that users can only be in one room at a time."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()
        
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePassword123!'
        )
        
        # Login the user
        self.client.login(username='testuser', password='SecurePassword123!')
    
    def test_user_can_create_first_room(self):
        """Test that a user can create their first room."""
        form_data = {
            'room_name': 'Test Room',
            'passphrase': 'password123',
            'nickname': 'TestPlayer',
            'game_type': '50',
            'lockout_mode': '1',
            'seed': '12345',
            'size': '5',
            'is_spectator': False,
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Create room with user
        room = form.create_room(user=self.user)
        
        # Verify room was created
        self.assertIsNotNone(room)
        self.assertEqual(room.name, 'Test Room')
        
        # Verify user's current_room is set
        self.user.refresh_from_db()
        self.assertEqual(self.user.current_room, room)
    
    def test_user_cannot_create_second_room(self):
        """Test that a user cannot create a second room while in another."""
        # Create first room
        form_data = {
            'room_name': 'First Room',
            'passphrase': 'password123',
            'nickname': 'TestPlayer',
            'game_type': '50',
            'lockout_mode': '1',
            'seed': '12345',
            'size': '5',
            'is_spectator': False,
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        first_room = form.create_room(user=self.user)
        
        # Try to create second room
        form_data['room_name'] = 'Second Room'
        form_data['seed'] = '54321'
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Should raise ValidationError
        with self.assertRaises(ValidationError) as context:
            form.create_room(user=self.user)
        
        # Check error message mentions the first room
        self.assertIn('First Room', str(context.exception))
    
    def test_user_cannot_join_second_room(self):
        """Test that a user cannot join a second room while in another."""
        # Create first room
        form_data = {
            'room_name': 'First Room',
            'passphrase': 'password123',
            'nickname': 'TestPlayer',
            'game_type': '50',
            'lockout_mode': '1',
            'seed': '12345',
            'size': '5',
            'is_spectator': False,
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        first_room = form.create_room(user=self.user)
        
        # Create second room (as a different user/anonymous)
        form_data['room_name'] = 'Second Room'
        form_data['seed'] = '54321'
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        second_room = form.create_room(user=None)  # Anonymous room creation
        
        # Try to join second room
        join_form_data = {
            'encoded_room_uuid': second_room.encoded_uuid,
            'room_name': second_room.name,
            'creator_name': second_room.creator.name,
            'game_name': second_room.current_game.game_type.long_name,
            'player_name': 'TestPlayer2',
            'passphrase': 'password123',
            'is_spectator': False,
        }
        join_form = JoinRoomForm(data=join_form_data)
        self.assertTrue(join_form.is_valid())
        
        # Should raise ValidationError
        with self.assertRaises(ValidationError) as context:
            join_form.create_player(user=self.user)
        
        # Check error message mentions the first room
        self.assertIn('First Room', str(context.exception))
    
    def test_user_can_rejoin_same_room(self):
        """Test that a user can rejoin the same room they're already in."""
        # Create room
        form_data = {
            'room_name': 'Test Room',
            'passphrase': 'password123',
            'nickname': 'TestPlayer',
            'game_type': '50',
            'lockout_mode': '1',
            'seed': '12345',
            'size': '5',
            'is_spectator': False,
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        room = form.create_room(user=self.user)
        
        # Try to join the same room again (should not raise error)
        join_form_data = {
            'encoded_room_uuid': room.encoded_uuid,
            'room_name': room.name,
            'creator_name': room.creator.name,
            'game_name': room.current_game.game_type.long_name,
            'player_name': 'TestPlayer2',
            'passphrase': 'password123',
            'is_spectator': False,
        }
        join_form = JoinRoomForm(data=join_form_data)
        self.assertTrue(join_form.is_valid())
        
        # Should not raise error since it's the same room
        player = join_form.create_player(user=self.user)
        self.assertIsNotNone(player)
    
    def test_leaving_room_clears_current_room(self):
        """Test that leaving a room clears the user's current_room."""
        # Create room
        form_data = {
            'room_name': 'Test Room',
            'passphrase': 'password123',
            'nickname': 'TestPlayer',
            'game_type': '50',
            'lockout_mode': '1',
            'seed': '12345',
            'size': '5',
            'is_spectator': False,
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        room = form.create_room(user=self.user)
        
        # Verify user is in the room
        self.user.refresh_from_db()
        self.assertEqual(self.user.current_room, room)
        
        # Leave the room
        disconnect_url = reverse('room_disconnect', kwargs={'encoded_room_uuid': room.encoded_uuid})
        response = self.client.get(disconnect_url)
        
        # Verify user's current_room is cleared
        self.user.refresh_from_db()
        self.assertIsNone(self.user.current_room)
    
    def test_anonymous_user_not_restricted(self):
        """Test that anonymous users are not restricted to one room."""
        # Logout
        self.client.logout()
        
        # Create first room as anonymous
        form_data = {
            'room_name': 'First Room',
            'passphrase': 'password123',
            'nickname': 'AnonPlayer',
            'game_type': '50',
            'lockout_mode': '1',
            'seed': '12345',
            'size': '5',
            'is_spectator': False,
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        first_room = form.create_room(user=None)
        
        # Create second room as anonymous (should not raise error)
        form_data['room_name'] = 'Second Room'
        form_data['seed'] = '54321'
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        second_room = form.create_room(user=None)
        
        # Both rooms should be created successfully
        self.assertIsNotNone(first_room)
        self.assertIsNotNone(second_room)
        self.assertNotEqual(first_room.uuid, second_room.uuid)
    
    def test_user_can_create_room_after_leaving(self):
        """Test that a user can create a new room after leaving the previous one."""
        # Create first room
        form_data = {
            'room_name': 'First Room',
            'passphrase': 'password123',
            'nickname': 'TestPlayer',
            'game_type': '50',
            'lockout_mode': '1',
            'seed': '12345',
            'size': '5',
            'is_spectator': False,
            'hide_card': False,
            'fog_of_war': False,
        }
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        first_room = form.create_room(user=self.user)
        
        # Leave the room
        disconnect_url = reverse('room_disconnect', kwargs={'encoded_room_uuid': first_room.encoded_uuid})
        self.client.get(disconnect_url)
        
        # Verify user's current_room is cleared
        self.user.refresh_from_db()
        self.assertIsNone(self.user.current_room)
        
        # Create second room (should succeed)
        form_data['room_name'] = 'Second Room'
        form_data['seed'] = '54321'
        form = RoomForm(data=form_data)
        self.assertTrue(form.is_valid())
        second_room = form.create_room(user=self.user)
        
        # Verify second room was created
        self.assertIsNotNone(second_room)
        self.assertEqual(second_room.name, 'Second Room')
        
        # Verify user's current_room is set to second room
        self.user.refresh_from_db()
        self.assertEqual(self.user.current_room, second_room)
