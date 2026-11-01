"""
The public, read-only JSON view of a room (GET /api/room/<encoded_room_uuid>).

Anyone with the room link can read it, so it is built from an allow-list: only
the fields below are ever copied out of the models. In particular it never
carries the room password, player/user UUIDs, socket keys, emails, chat, or a
counter's saved snapshot and dismissed alerts. The seed is left out while the
room is active and has a Gamemaster, and the card (and with it the counters'
goal lists) is left out while it is still hidden.
"""
from bingosync.models.colors import Color
from bingosync.models.enums import Role
from bingosync.models.rooms import COUNTED_CLAIM_STATUSES, CounterTally


def board_lines(size):
    """Every row, column and diagonal of a size x size board as 1-indexed
    slot lists."""
    lines = [[r * size + c + 1 for c in range(size)] for r in range(size)]
    lines += [[r * size + c + 1 for r in range(size)] for c in range(size)]
    lines.append([i * size + i + 1 for i in range(size)])
    lines.append([i * size + (size - 1 - i) + 1 for i in range(size)])
    return lines


def _scores(game, squares):
    """Per color: squares held and lines completed. Counts the same marks as a
    win or a bingo does (COUNTED_CLAIM_STATUSES)."""
    slots_by_color = {}
    for square in squares:
        if square.claim_status not in COUNTED_CLAIM_STATUSES:
            continue
        for color in square.color.colors:
            if color != Color.blank:
                slots_by_color.setdefault(color, set()).add(square.slot)
    lines = board_lines(game.size)
    return {
        color.name: {
            "squares": len(slots),
            "lines": sum(1 for line in lines if all(s in slots for s in line)),
        }
        for color, slots in sorted(slots_by_color.items(),
                                   key=lambda item: item[0].value)
    }


def _card(game, squares):
    return {
        "size": game.size,
        "squares": [{
            "slot": square.slot,
            "name": square.goal,
            "colors": [c.name for c in square.color.colors],
            "claim_status": square.claim_status,
        } for square in squares],
    }


def _counter(counter, game, squares, show_goals):
    color = counter.monitoring_color
    data = {
        "name": counter.name,
        "color": color.name if color else None,
        "goals": [],
    }
    if color is None or not show_goals:
        return data
    tally = CounterTally.objects.filter(
        game=game, counter=counter, color_value=color.value).first()
    counts = tally.counts if tally else {}
    data["goals"] = [{
        "slot": square.slot,
        "count": counts.get(str(square.slot), 0),
        "amount": square.amount,
    } for square in squares if square.is_counted]
    return data


def room_public_json(room):
    """The room as a dict, or None if it has no game yet.

    Counters' live goal counts are included on purpose (issue #20: stream
    overlays); they stay hidden from players and spectators inside the site.
    `scores` count only marks that count toward a win (confirmed or under
    review), so a legacy 'rejected' mark shows on the card but not in scores.
    """
    game = room.current_game
    if game is None:
        return None
    squares = list(game.squares)
    card_visible = not room.is_seed_hidden
    # The room-wide rule for the seed, plus: it would reveal a hidden card.
    # A finished room (inactive) shows its seed even under a Gamemaster.
    seed_visible = card_visible and (
        not room.active or room.seed_visible_to(None))

    players = list(room.players)
    winner = game.winner
    return {
        "room": {
            "name": room.name,
            "game": str(game.game_type.group),
            "variant": str(game.game_type),
            "lockout_mode": str(game.lockout_mode),
            "fog_of_war": game.fog_of_war,
            "card_hidden": not card_visible,
            "active": room.active,
            "seed": game.seed if seed_visible else None,
            "winner": ({"name": winner.name, "color": winner.color.name}
                       if winner else None),
        },
        "card": _card(game, squares) if card_visible else None,
        "players": [{
            "name": player.name,
            "color": player.color.name,
            "role": player.role,
            "connected": player.connected,
        } for player in players],
        "scores": _scores(game, squares),
        "counters": [
            _counter(player, game, squares, card_visible)
            for player in players if player.role == Role.COUNTER],
    }
