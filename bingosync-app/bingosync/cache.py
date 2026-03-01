"""
Cache utilities for HP Bingo Platform.

This module provides caching functions for frequently accessed data:
- Room settings (5 minute TTL)
- Player lists (1 minute TTL)
- Generated boards by seed (24 hour TTL)
"""

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)


# Cache key prefixes
ROOM_SETTINGS_PREFIX = 'room_settings'
PLAYER_LIST_PREFIX = 'player_list'
BOARD_SEED_PREFIX = 'board'

# Cache timeouts (in seconds)
ROOM_SETTINGS_TIMEOUT = 300  # 5 minutes
PLAYER_LIST_TIMEOUT = 60     # 1 minute
BOARD_SEED_TIMEOUT = 86400   # 24 hours


def get_room_settings_cache_key(room_uuid):
    """Generate cache key for room settings."""
    return f'{ROOM_SETTINGS_PREFIX}:{room_uuid}'


def get_player_list_cache_key(room_uuid):
    """Generate cache key for player list."""
    return f'{PLAYER_LIST_PREFIX}:{room_uuid}'


def get_board_cache_key(seed):
    """Generate cache key for board by seed."""
    return f'{BOARD_SEED_PREFIX}:{seed}'


def get_room_settings(room):
    """
    Get room settings with caching.
    
    Args:
        room: Room instance
        
    Returns:
        dict: Room settings dictionary
    """
    cache_key = get_room_settings_cache_key(room.uuid)
    settings = cache.get(cache_key)
    
    if settings is None:
        logger.debug(f"Cache miss for room settings: {room.uuid}")
        settings = room.settings
        cache.set(cache_key, settings, timeout=ROOM_SETTINGS_TIMEOUT)
    else:
        logger.debug(f"Cache hit for room settings: {room.uuid}")
    
    return settings


def get_player_list(room):
    """
    Get player list with caching.
    
    Args:
        room: Room instance
        
    Returns:
        list: List of Player instances
    """
    cache_key = get_player_list_cache_key(room.uuid)
    players = cache.get(cache_key)
    
    if players is None:
        logger.debug(f"Cache miss for player list: {room.uuid}")
        # Convert queryset to list to make it cacheable
        players = list(room.players)
        cache.set(cache_key, players, timeout=PLAYER_LIST_TIMEOUT)
    else:
        logger.debug(f"Cache hit for player list: {room.uuid}")
    
    return players


def get_board_by_seed(seed, generator_func):
    """
    Get generated board by seed with caching.
    
    Args:
        seed: Board seed value
        generator_func: Function to generate board if not cached
        
    Returns:
        Board data (format depends on generator)
    """
    cache_key = get_board_cache_key(seed)
    board = cache.get(cache_key)
    
    if board is None:
        logger.debug(f"Cache miss for board seed: {seed}")
        board = generator_func(seed)
        cache.set(cache_key, board, timeout=BOARD_SEED_TIMEOUT)
    else:
        logger.debug(f"Cache hit for board seed: {seed}")
    
    return board


def invalidate_room_settings_cache(room_uuid):
    """
    Invalidate room settings cache.
    
    Args:
        room_uuid: Room UUID
    """
    cache_key = get_room_settings_cache_key(room_uuid)
    cache.delete(cache_key)
    logger.debug(f"Invalidated room settings cache: {room_uuid}")


def invalidate_player_list_cache(room_uuid):
    """
    Invalidate player list cache.
    
    Args:
        room_uuid: Room UUID
    """
    cache_key = get_player_list_cache_key(room_uuid)
    cache.delete(cache_key)
    logger.debug(f"Invalidated player list cache: {room_uuid}")


def invalidate_room_cache(room_uuid):
    """
    Invalidate all caches for a room.
    
    Args:
        room_uuid: Room UUID
    """
    invalidate_room_settings_cache(room_uuid)
    invalidate_player_list_cache(room_uuid)
    logger.debug(f"Invalidated all caches for room: {room_uuid}")


# Signal handlers for automatic cache invalidation
# These will be connected in apps.py ready() method

def invalidate_on_room_change(sender, instance, **kwargs):
    """Invalidate room caches when Room model changes."""
    invalidate_room_settings_cache(instance.uuid)


def invalidate_on_game_change(sender, instance, **kwargs):
    """Invalidate room settings cache when Game model changes."""
    if hasattr(instance, 'room'):
        invalidate_room_settings_cache(instance.room.uuid)


def invalidate_on_player_change(sender, instance, **kwargs):
    """Invalidate player list cache when Player model changes."""
    invalidate_player_list_cache(instance.room.uuid)


def connect_cache_signals():
    """
    Connect signal handlers for automatic cache invalidation.
    
    This should be called from AppConfig.ready() to ensure signals
    are connected after all models are loaded.
    """
    from bingosync.models.rooms import Room, Game, Player
    
    # Room changes invalidate room settings
    post_save.connect(invalidate_on_room_change, sender=Room)
    
    # Game changes invalidate room settings
    post_save.connect(invalidate_on_game_change, sender=Game)
    
    # Player changes invalidate player list
    post_save.connect(invalidate_on_player_change, sender=Player)
    post_delete.connect(invalidate_on_player_change, sender=Player)
    
    logger.info("Cache invalidation signals connected")
