"""
Tests for system chat messages for role and counter events (Task 3.16).
"""

from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.events import ChatEvent, RoleChangeEvent, CounterAssignmentEvent
from bingosync.models.enums import Role
from bingosync.models.game_type import GameType
from bingosync.models.colors import Color
import json

User = get_user_model()


# Use locmem cache for testing instead of Redis
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-test-cache-system-chat',
    }
})
@patch('bingosync.publish.requests.put')
class SystemChatMessagesTestCase(TestCase):
    """Test system chat messages for role and counter events."""

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
        self.counter_user = User.objects.create_user(
            username='counter1',
            email='counter1@test.com',
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
            user=self.gm_user,
            name='Gamemaster',
            role=Role.GAMEMASTER,
            color_value=Color.orange.value
        )

        # Create regular player
        self.regular_player = Player.objects.create(
            room=self.room,
            user=self.player_user,
            name='Player1',
            role=Role.PLAYER,
            color_value=Color.blue.value
        )

        # Create counter player
        self.counter_player = Player.objects.create(
            room=self.room,
            user=self.counter_user,
            name='Counter1',
            role=Role.COUNTER,
            color_value=Color.green.value
        )

        self.client = Client()

    def test_role_change_creates_system_chat_message(self, mock_put):
        """Test that role change creates a system chat message."""
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

        # Verify system chat message was created
        system_messages = ChatEvent.objects.filter(
            player=self.gm_player,
            is_system_message=True
        )
        self.assertEqual(system_messages.count(), 1)

        message = system_messages.first()
        self.assertIn('Player1', message.body)
        self.assertIn('Counter', message.body)
        self.assertIn('role', message.body.lower())

    def test_counter_assignment_creates_system_chat_message(self, mock_put):
        """Test that counter assignment creates a system chat message."""
        # Login as gamemaster
        self.client.force_login(self.gm_user)

        # Store session player
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()

        # Assign counter to monitor player
        response = self.client.post(
            '/api/assign-counter',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'counter_player_uuid': self.counter_player.encoded_uuid,
                'monitored_player_uuid': self.regular_player.encoded_uuid
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify system chat message was created
        system_messages = ChatEvent.objects.filter(
            player=self.gm_player,
            is_system_message=True
        )
        self.assertEqual(system_messages.count(), 1)

        message = system_messages.first()
        self.assertIn('Counter1', message.body)
        self.assertIn('Player1', message.body)
        self.assertIn('monitoring', message.body.lower())

    def test_counter_unassignment_creates_system_chat_message(self, mock_put):
        """Test that counter unassignment creates a system chat message."""
        # First assign counter
        self.counter_player.monitoring_player = self.regular_player
        self.counter_player.save()

        # Login as gamemaster
        self.client.force_login(self.gm_user)

        # Store session player
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()

        # Unassign counter (set monitored_player_uuid to null)
        response = self.client.post(
            '/api/assign-counter',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'counter_player_uuid': self.counter_player.encoded_uuid,
                'monitored_player_uuid': 'null'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify system chat message was created
        system_messages = ChatEvent.objects.filter(
            player=self.gm_player,
            is_system_message=True
        )
        self.assertEqual(system_messages.count(), 1)

        message = system_messages.first()
        self.assertIn('Counter1', message.body)
        self.assertIn('no longer', message.body.lower())

    def test_system_message_to_json_includes_flag(self, mock_put):
        """Test that system message JSON includes is_system_message flag."""
        # Create a system chat message
        chat_event = ChatEvent.objects.create(
            player=self.gm_player,
            player_color_value=self.gm_player.color.value,
            body='Test system message',
            is_system_message=True
        )

        # Get JSON representation
        json_data = chat_event.to_json()

        # Verify structure
        self.assertEqual(json_data['type'], 'chat')
        self.assertEqual(json_data['text'], 'Test system message')
        self.assertTrue(json_data['is_system_message'])

    def test_regular_chat_message_not_system(self, mock_put):
        """Test that regular chat messages are not marked as system messages."""
        # Create a regular chat message
        chat_event = ChatEvent.objects.create(
            player=self.regular_player,
            player_color_value=self.regular_player.color.value,
            body='Regular chat message',
            is_system_message=False
        )

        # Get JSON representation
        json_data = chat_event.to_json()

        # Verify structure
        self.assertEqual(json_data['type'], 'chat')
        self.assertEqual(json_data['text'], 'Regular chat message')
        self.assertFalse(json_data['is_system_message'])

    def test_system_message_has_timestamp(self, mock_put):
        """Test that system messages include timestamp."""
        # Login as gamemaster
        self.client.force_login(self.gm_user)

        # Store session player
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: self.gm_player.encoded_uuid
        }
        session.save()

        # Change role to trigger system message
        response = self.client.post(
            '/api/assign-role',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': self.regular_player.encoded_uuid,
                'new_role': Role.SPECTATOR
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify system chat message has timestamp
        system_message = ChatEvent.objects.filter(
            player=self.gm_player,
            is_system_message=True
        ).first()

        self.assertIsNotNone(system_message)
        self.assertIsNotNone(system_message.timestamp)

        # Verify JSON includes timestamp
        json_data = system_message.to_json()
        self.assertIn('timestamp', json_data)
        self.assertIsNotNone(json_data['timestamp'])
