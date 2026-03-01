"""
Rate limiting decorators for Bingosync views.

This module provides rate limiting decorators using django-ratelimit
to protect against brute force attacks and DoS.
"""

from functools import wraps
from django.http import HttpResponse, HttpResponseForbidden
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited


def ratelimit_login(view_func):
    """
    Rate limit login attempts to 10 per minute per IP address.

    This prevents brute force password attacks.
    """
    @wraps(view_func)
    @ratelimit(key='ip', rate='10/m', method='POST', block=True)
    def wrapped(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapped


def ratelimit_registration(view_func):
    """
    Rate limit registration attempts to 5 per minute per IP address.

    This prevents spam account creation.
    """
    @wraps(view_func)
    @ratelimit(key='ip', rate='5/m', method='POST', block=True)
    def wrapped(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapped


def ratelimit_authenticated_action(view_func):
    """
    Rate limit authenticated actions to 100 per hour per user.

    This prevents abuse of authenticated endpoints.
    Uses IP as fallback for unauthenticated requests.
    """
    @wraps(view_func)
    @ratelimit(key='user_or_ip', rate='100/h', method='POST', block=True)
    def wrapped(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    return wrapped


def handle_ratelimit(view_func):
    """
    Decorator to handle rate limit exceptions and return 429 Too Many Requests.

    Should be applied as the outermost decorator.
    """
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Ratelimited:
            return HttpResponse(
                "Rate limit exceeded. Please try again later.",
                status=429,
                content_type="text/plain"
            )
    return wrapped


def require_permission(action):
    """
    Decorator to require a specific permission for a view.

    This decorator checks if the player (retrieved from session) has
    permission to perform the specified action based on their role.

    Usage:
        @require_permission('mark_square')
        def goal_selected(request):
            ...

    Args:
        action: String representing the required action permission

    Returns:
        Decorator function that checks permission before executing view
    """
    from bingosync.permissions import check_permission

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            # The view should have already retrieved the player
            # We'll check if it's available in the request context
            player = getattr(request, 'player', None)

            if not player:
                return HttpResponseForbidden(
                    "Authentication required to perform this action."
                )

            if not check_permission(player, action):
                return HttpResponseForbidden(
                    f"You do not have permission to {action.replace('_', ' ')}."
                )

            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator
