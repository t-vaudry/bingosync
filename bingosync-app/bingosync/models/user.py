from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Persistent user account extending Django's AbstractUser.
    
    Tracks user statistics for gameplay and enforces one room at a time.
    """
    # Override email field to make it unique
    email = models.EmailField(
        verbose_name='email address',
        max_length=254,
        unique=True,
        blank=False,
        help_text='Required. Must be unique across all users.'
    )
    # Enforce one room at a time
    current_room = models.ForeignKey(
        'Room',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='current_users',
        help_text='The room the user is currently in (one room at a time)'
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Statistics fields
    total_games_played = models.IntegerField(
        default=0,
        help_text='Total number of games completed'
    )
    total_squares_marked = models.IntegerField(
        default=0,
        help_text='Total number of squares marked across all games'
    )
    total_bingos_completed = models.IntegerField(
        default=0,
        help_text='Total number of bingos completed'
    )
    wins = models.IntegerField(
        default=0,
        help_text='Number of wins in lockout mode'
    )
    losses = models.IntegerField(
        default=0,
        help_text='Number of losses in lockout mode'
    )
    
    class Meta:
        db_table = 'bingosync_user'
        indexes = [
            models.Index(fields=['username']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return self.username
    
    def __repr__(self):
        return f"<User: id={self.id!r}, username={self.username!r}>"
    
    @property
    def win_rate(self):
        """Calculate win rate in lockout mode games."""
        total_lockout_games = self.wins + self.losses
        if total_lockout_games == 0:
            return 0.0
        return (self.wins / total_lockout_games) * 100
