"""
Achievement definitions and lazy evaluation.

Achievements are computed on demand from a user's stored stats and their
CompletedLine records -- nothing is written during gameplay. Each definition
has a check(user, ctx) predicate; `ctx` precomputes the line-pattern lookups
once so evaluating a whole profile runs only a couple of extra queries.
"""
from django.db.models import Count

from bingosync.models.rooms import CompletedLine


def _user_context(user):
    """Precompute the CompletedLine-derived facts an evaluation needs."""
    lines = CompletedLine.objects.filter(player__user=user)
    kinds = set(lines.values_list('line', flat=True))
    # A blackout is claiming a whole board, i.e. all five rows in one game.
    blackout = (
        lines.filter(line__startswith='row-')
        .values('game')
        .annotate(n=Count('line', distinct=True))
        .filter(n__gte=5)
        .exists())
    return {
        'has_row': any(k.startswith('row-') for k in kinds),
        'has_col': any(k.startswith('col-') for k in kinds),
        'has_diag': any(k.startswith('diag-') for k in kinds),
        'blackout': blackout,
    }


ACHIEVEMENTS = [
    {"code": "first_square", "icon": "\U0001F3B2", "name": "First Steps",
     "desc": "Mark your first square",
     "check": lambda u, c: u.total_squares_marked >= 1},
    {"code": "hundred_squares", "icon": "\U0001F3AF", "name": "Getting the Hang of It",
     "desc": "Mark 100 squares",
     "check": lambda u, c: u.total_squares_marked >= 100},
    {"code": "many_squares", "icon": "\U0001F396️", "name": "Board Veteran",
     "desc": "Mark 500 squares",
     "check": lambda u, c: u.total_squares_marked >= 500},
    {"code": "ten_games", "icon": "\U0001F501", "name": "Regular",
     "desc": "Finish 10 games",
     "check": lambda u, c: u.total_games_played >= 10},
    {"code": "first_win", "icon": "\U0001F3C6", "name": "First Win",
     "desc": "Win a lockout game",
     "check": lambda u, c: u.wins >= 1},
    {"code": "ten_wins", "icon": "\U0001F451", "name": "Champion",
     "desc": "Win 10 lockout games",
     "check": lambda u, c: u.wins >= 10},
    {"code": "first_bingo", "icon": "⭐", "name": "Bingo!",
     "desc": "Complete your first line",
     "check": lambda u, c: u.total_bingos_completed >= 1},
    {"code": "many_bingos", "icon": "\U0001F4CA", "name": "Line Master",
     "desc": "Complete 25 lines",
     "check": lambda u, c: u.total_bingos_completed >= 25},
    {"code": "row", "icon": "➡️", "name": "Full Row",
     "desc": "Complete a full row",
     "check": lambda u, c: c["has_row"]},
    {"code": "column", "icon": "⬇️", "name": "Full Column",
     "desc": "Complete a full column",
     "check": lambda u, c: c["has_col"]},
    {"code": "diagonal", "icon": "↗️", "name": "Diagonal",
     "desc": "Complete a diagonal",
     "check": lambda u, c: c["has_diag"]},
    {"code": "blackout", "icon": "⬛", "name": "Blackout",
     "desc": "Claim an entire board",
     "check": lambda u, c: c["blackout"]},
]


def evaluate_achievements(user):
    """Return every achievement with an `earned` flag for `user`."""
    ctx = _user_context(user)
    return [
        {"code": a["code"], "icon": a["icon"], "name": a["name"],
         "desc": a["desc"], "earned": a["check"](user, ctx)}
        for a in ACHIEVEMENTS
    ]
