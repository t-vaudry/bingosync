from django.db import models


class Role(models.TextChoices):
    """Player roles in a room"""
    GAMEMASTER = 'gamemaster', 'Gamemaster'
    PLAYER = 'player', 'Player'
    COUNTER = 'counter', 'Counter'
    SPECTATOR = 'spectator', 'Spectator'
