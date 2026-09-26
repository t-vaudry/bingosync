"""
Role-based permissions system for HP Bingo Platform.

This module defines permissions for each role and provides
a check_permission() function to validate actions.
"""

from bingosync.models.enums import Role


# Permission definitions for each role
ROLE_PERMISSIONS = {
    Role.GAMEMASTER: {
        'mark_square': True,  # Gamemaster can mark squares
        'generate_board': True,
        'reveal_fog': True,
        'assign_roles': True,
        'remove_players': True,
        'delete_room': True,
        'view_board': True,
        'chat': True,
    },
    Role.PLAYER: {
        'mark_square': True,
        'view_board': True,
        'chat': True,
    },
    Role.COUNTER: {
        'view_board': True,
        'review_claims': True,
        'chat': True,
    },
    Role.SPECTATOR: {
        'view_board': True,
        'chat': True,
    },
}


def check_permission(player, action):
    """
    Check if a player has permission to perform an action.

    Args:
        player: Player instance with role field
        action: String representing the action (e.g., 'mark_square', 'generate_board')

    Returns:
        Boolean indicating whether the player has permission

    Examples:
        >>> check_permission(gamemaster_player, 'generate_board')
        True
        >>> check_permission(gamemaster_player, 'mark_square')
        True
        >>> check_permission(spectator_player, 'mark_square')
        False
    """
    if not player or not hasattr(player, 'role'):
        return False

    # Get permissions for the player's role
    permissions = ROLE_PERMISSIONS.get(player.role, {})

    # Check if the action is in the role's permissions
    return permissions.get(action, False)


def can_generate_board(player):
    """Whether a player may generate a new board (card).

    Allowed for the Gamemaster, and for any Player when the room has no
    Gamemaster -- so a room created without a GM isn't stuck with one board,
    while GM-run rooms keep board control with the GM.
    """
    if not player or not hasattr(player, 'role'):
        return False
    if player.role == Role.GAMEMASTER:
        return True
    if player.role == Role.PLAYER:
        from bingosync.models.rooms import Player
        room_has_gamemaster = Player.objects.filter(
            room=player.room, role=Role.GAMEMASTER).exists()
        return not room_has_gamemaster
    return False


def require_permission(action):
    """
    Decorator to require a specific permission for a view.

    Usage:
        @require_permission('mark_square')
        def goal_selected(request):
            ...

    Args:
        action: String representing the required action permission

    Returns:
        Decorator function that checks permission before executing view
    """
    from functools import wraps
    from django.http import HttpResponseForbidden

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            # Get player from session or request context
            # This assumes the view has already authenticated the player
            player = getattr(request, 'player', None)

            if not player or not check_permission(player, action):
                return HttpResponseForbidden(
                    f"You do not have permission to {action.replace('_', ' ')}."
                )

            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
