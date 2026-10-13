from django.contrib.auth.models import AbstractUser
from django.db import models


class ReviewStyle(models.TextChoices):
    """How a counter approves or rejects goals they've put in review.
    Every style puts a goal in review with a right-click, and the review
    list's Approve/Reject buttons always work."""
    LIST = 'list', 'Right-click again to approve; reject from the review list'
    CLICK = 'click', 'Left-click to reject, right-click to approve'
    HOVER = 'hover', 'Hover for a reject button, right-click to approve'
    BUTTONS = 'buttons', 'Approve and reject buttons on the goal (right-click does nothing)'


class User(AbstractUser):
    """
    Persistent user account extending Django's AbstractUser.

    Tracks user statistics for gameplay and enforces one room at a time.
    """
    # Override email field to make it unique and optional
    email = models.EmailField(
        verbose_name='email address',
        max_length=254,
        unique=True,
        blank=True,
        null=True,
        help_text='Optional. Must be unique if provided.'
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

    # Preferences
    review_style = models.CharField(
        max_length=16,
        choices=ReviewStyle.choices,
        default=ReviewStyle.LIST,
        help_text='How this user approves or rejects goals in review as a counter'
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
