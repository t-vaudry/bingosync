"""
Django app configuration for bingosync.
"""

from django.apps import AppConfig


class BingosyncConfig(AppConfig):
    """Configuration for the bingosync Django app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bingosync'
    
    def ready(self):
        """
        Initialize app when Django starts.
        
        This method is called once Django has loaded all models.
        We use it to connect cache invalidation signals.
        """
        # Import and connect cache signals
        from bingosync.cache import connect_cache_signals
        connect_cache_signals()
