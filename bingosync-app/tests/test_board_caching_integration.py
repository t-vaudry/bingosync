"""
Integration tests for board caching by seed.

Tests that board generation is properly cached when using the same seed.
"""

from django.test import TestCase, override_settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from bingosync.models.rooms import Room, Game
from bingosync.models.game_type import GameType
from bingosync.forms import RoomForm
from bingosync.cache import get_board_cache_key
from unittest.mock import patch, MagicMock

User = get_user_model()


# Use locmem cache for testing instead of Redis
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
})
class BoardCachingIntegrationTest(TestCase):
    """Test cases for board caching integration."""
    
    def setUp(self):
        """Set up test data."""
        # Clear cache before each test
        cache.clear()
        
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    
    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
    
    def test_board_cached_on_room_creation(self):
        """Test that board is cached when creating a room with a seed."""
        seed = 12345
        
        # Create room with specific seed
        form_data = {
            'room_name': 'Test Room',
            'passphrase': 'test123',
            'game_type': GameType.hp_cos.value,
            'lockout_mode': 1,
            'seed': seed,
            'hide_card': False,
            'fog_of_war': False,
            'gamemaster_only': False,
        }
        
        form = RoomForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid(), f"Form errors: {form.errors}")
        
        # Create the room (should cache the board)
        room = form.create_room(user=self.user)
        
        # Verify room was created
        self.assertIsNotNone(room)
        self.assertEqual(room.current_game.seed, seed)
        
        # Verify board is cached
        cache_key = get_board_cache_key(seed)
        cached_board = cache.get(cache_key)
        self.assertIsNotNone(cached_board, "Board should be cached after room creation")
        
        # Verify cached board is a tuple (seed, board_json)
        self.assertIsInstance(cached_board, tuple)
        self.assertEqual(len(cached_board), 2)
        cached_seed, cached_board_json = cached_board
        # Seed may be string or int, so compare as strings
        self.assertEqual(str(cached_seed), str(seed))
        self.assertEqual(len(cached_board_json), 25)
    
    def test_board_cache_reused_on_second_room(self):
        """Test that cached board is reused when creating another room with same seed."""
        seed = 54321
        
        # Mock the generator to track calls
        original_get_card = GameType.hp_cos.generator_instance().get_card
        call_count = [0]
        
        def mock_get_card(*args, **kwargs):
            call_count[0] += 1
            return original_get_card(*args, **kwargs)
        
        with patch.object(
            GameType.hp_cos.generator_instance().__class__,
            'get_card',
            side_effect=mock_get_card
        ):
            # Create first room
            form_data1 = {
                'room_name': 'Test Room 1',
                'passphrase': 'test123',
                'game_type': GameType.hp_cos.value,
                'lockout_mode': 1,
                'seed': seed,
                'hide_card': False,
                'fog_of_war': False,
                'gamemaster_only': False,
            }
            
            form1 = RoomForm(data=form_data1, user=self.user)
            self.assertTrue(form1.is_valid())
            room1 = form1.create_room(user=self.user)
            
            # Generator should be called once
            self.assertEqual(call_count[0], 1)
            
            # Leave the room so we can create another
            self.user.current_room = None
            self.user.save()
            
            # Create second room with same seed
            form_data2 = {
                'room_name': 'Test Room 2',
                'passphrase': 'test456',
                'game_type': GameType.hp_cos.value,
                'lockout_mode': 1,
                'seed': seed,
                'hide_card': False,
                'fog_of_war': False,
                'gamemaster_only': False,
            }
            
            form2 = RoomForm(data=form_data2, user=self.user)
            self.assertTrue(form2.is_valid())
            room2 = form2.create_room(user=self.user)
            
            # Generator should still be called only once (cache hit)
            self.assertEqual(call_count[0], 1, "Generator should not be called again for cached seed")
            
            # Verify both rooms have the same board
            self.assertEqual(room1.current_game.board, room2.current_game.board)
    
    def test_random_seed_not_cached(self):
        """Test that boards with empty/random seeds are not cached."""
        # Create room with empty seed (random)
        form_data = {
            'room_name': 'Random Room',
            'passphrase': 'test123',
            'game_type': GameType.hp_cos.value,
            'lockout_mode': 1,
            'seed': '',  # Empty seed = random
            'hide_card': False,
            'fog_of_war': False,
            'gamemaster_only': False,
        }
        
        form = RoomForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())
        room = form.create_room(user=self.user)
        
        # Verify room was created with a random seed
        self.assertIsNotNone(room)
        self.assertNotEqual(room.current_game.seed, '')
        
        # Verify empty seed is not cached
        cache_key = get_board_cache_key('')
        cached_board = cache.get(cache_key)
        self.assertIsNone(cached_board, "Empty seed should not be cached")
    
    def test_cache_key_format(self):
        """Test that cache key format is exactly 'board:{seed}'."""
        seed = 99999
        expected_key = f'board:{seed}'
        
        # Get the actual cache key
        actual_key = get_board_cache_key(seed)
        
        # Verify format
        self.assertEqual(actual_key, expected_key)
    
    def test_cache_ttl_is_24_hours(self):
        """Test that board cache TTL is 24 hours (86400 seconds)."""
        from bingosync.cache import BOARD_SEED_TIMEOUT
        
        # Verify TTL is 24 hours
        self.assertEqual(BOARD_SEED_TIMEOUT, 86400)
