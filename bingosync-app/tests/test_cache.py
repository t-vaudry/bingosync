"""
Tests for Redis caching functionality.

Note: These tests use Django's locmem cache backend for testing.
In production, Redis will be used as configured in settings.py.
"""

from django.test import TestCase, override_settings
from django.core.cache import cache
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.game_type import GameType
from bingosync.models.enums import Role
from bingosync.cache import (
    get_room_settings,
    get_player_list,
    get_board_by_seed,
    invalidate_room_settings_cache,
    invalidate_player_list_cache,
    invalidate_room_cache,
    get_room_settings_cache_key,
    get_player_list_cache_key,
    get_board_cache_key,
)


# Use locmem cache for testing instead of Redis
@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
})


class CacheTestCase(TestCase):
    """Test cases for caching functionality."""
    
    def setUp(self):
        """Set up test data."""
        # Clear cache before each test
        cache.clear()
        
        # Create test room
        self.room = Room.objects.create(
            name="Test Room",
            passphrase="test123",
            hide_card=False
        )
        
        # Create test game
        board_json = [{"name": f"Goal {i}", "tier": 1} for i in range(1, 26)]
        self.game = Game.from_board(
            board_json,
            room=self.room,
            seed=12345,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=1,
            fog_of_war=False
        )
        
        # Room.current_game is a property that returns the latest game automatically
        # No need to set it manually
        
        # Create test players
        self.player1 = Player.objects.create(
            room=self.room,
            name="Player 1",
            role=Role.PLAYER
        )
        
        self.player2 = Player.objects.create(
            room=self.room,
            name="Player 2",
            role=Role.PLAYER
        )
    
    def tearDown(self):
        """Clean up after tests."""
        cache.clear()
    
    def test_room_settings_cache_hit(self):
        """Test that room settings are cached on second access."""
        # First call should miss cache
        settings1 = get_room_settings(self.room)
        
        # Verify settings are correct
        self.assertEqual(settings1['seed'], 12345)
        self.assertEqual(settings1['hide_card'], False)
        self.assertEqual(settings1['fog_of_war'], False)
        
        # Second call should hit cache
        cache_key = get_room_settings_cache_key(self.room.uuid)
        cached_value = cache.get(cache_key)
        self.assertIsNotNone(cached_value)
        
        settings2 = get_room_settings(self.room)
        self.assertEqual(settings1, settings2)
    
    def test_room_settings_cache_invalidation(self):
        """Test that room settings cache is invalidated on changes."""
        # Cache the settings
        settings1 = get_room_settings(self.room)
        
        # Verify cache exists
        cache_key = get_room_settings_cache_key(self.room.uuid)
        self.assertIsNotNone(cache.get(cache_key))
        
        # Invalidate cache
        invalidate_room_settings_cache(self.room.uuid)
        
        # Verify cache is cleared
        self.assertIsNone(cache.get(cache_key))
    
    def test_player_list_cache_hit(self):
        """Test that player list is cached on second access."""
        # First call should miss cache
        players1 = get_player_list(self.room)
        
        # Verify players are correct
        self.assertEqual(len(players1), 2)
        self.assertEqual(players1[0].name, "Player 1")
        self.assertEqual(players1[1].name, "Player 2")
        
        # Second call should hit cache
        cache_key = get_player_list_cache_key(self.room.uuid)
        cached_value = cache.get(cache_key)
        self.assertIsNotNone(cached_value)
        
        players2 = get_player_list(self.room)
        self.assertEqual(len(players1), len(players2))
    
    def test_player_list_cache_invalidation(self):
        """Test that player list cache is invalidated on changes."""
        # Cache the player list
        players1 = get_player_list(self.room)
        
        # Verify cache exists
        cache_key = get_player_list_cache_key(self.room.uuid)
        self.assertIsNotNone(cache.get(cache_key))
        
        # Invalidate cache
        invalidate_player_list_cache(self.room.uuid)
        
        # Verify cache is cleared
        self.assertIsNone(cache.get(cache_key))
    
    def test_board_cache_by_seed(self):
        """Test that boards are cached by seed."""
        seed = 12345
        
        # Mock generator function
        call_count = [0]
        def mock_generator(seed):
            call_count[0] += 1
            return [f"Goal {i}" for i in range(25)]
        
        # First call should generate board
        board1 = get_board_by_seed(seed, mock_generator)
        self.assertEqual(call_count[0], 1)
        self.assertEqual(len(board1), 25)
        
        # Second call should use cache
        board2 = get_board_by_seed(seed, mock_generator)
        self.assertEqual(call_count[0], 1)  # Generator not called again
        self.assertEqual(board1, board2)
        
        # Verify cache exists
        cache_key = get_board_cache_key(seed)
        self.assertIsNotNone(cache.get(cache_key))
    
    def test_invalidate_all_room_caches(self):
        """Test that all room caches are invalidated together."""
        # Cache both settings and player list
        get_room_settings(self.room)
        get_player_list(self.room)
        
        # Verify both caches exist
        settings_key = get_room_settings_cache_key(self.room.uuid)
        players_key = get_player_list_cache_key(self.room.uuid)
        self.assertIsNotNone(cache.get(settings_key))
        self.assertIsNotNone(cache.get(players_key))
        
        # Invalidate all caches
        invalidate_room_cache(self.room.uuid)
        
        # Verify both caches are cleared
        self.assertIsNone(cache.get(settings_key))
        self.assertIsNone(cache.get(players_key))
    
    def test_cache_timeout_settings(self):
        """Test that cache keys have correct timeout values."""
        from bingosync.cache import (
            ROOM_SETTINGS_TIMEOUT,
            PLAYER_LIST_TIMEOUT,
            BOARD_SEED_TIMEOUT
        )
        
        # Verify timeout values match requirements
        self.assertEqual(ROOM_SETTINGS_TIMEOUT, 300)  # 5 minutes
        self.assertEqual(PLAYER_LIST_TIMEOUT, 60)     # 1 minute
        self.assertEqual(BOARD_SEED_TIMEOUT, 86400)   # 24 hours
