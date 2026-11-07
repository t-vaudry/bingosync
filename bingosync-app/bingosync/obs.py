"""Resolving a user's permanent OBS link to the room and player it shows."""
from bingosync.models.events import RevealedEvent
from bingosync.models.rooms import CardReveal, Player


def obs_target(user):
    """The Player whose room the user's OBS link currently shows, or None.

    Among the rooms the user is connected to (and that are still active), the
    link sticks to the room it already shows: joining or creating another room
    never takes it over. Only when that room is gone (or none was ever chosen)
    does it move to the most recently joined one, and it stays there.
    """
    players = [
        player for player in
        Player.objects.filter(user=user, room__active=True)
        .select_related("room").order_by("-created_date")
        if player.connected
    ]
    if not players:
        return None
    for player in players:
        if user.obs_room_id == player.room_id:
            return player
    chosen = players[0]
    user.obs_room_id = chosen.room_id
    user.save(update_fields=["obs_room"])
    return chosen


def board_hidden_for(player):
    """Whether `player` still has the board covered (hide-card rooms only).

    The card is uncovered for the current game once this player reveals it
    (CardReveal) or the Gamemaster reveals it for the room (RevealedEvent).
    The room page and the player's OBS source both use this, so they agree.
    """
    room = player.room
    if not room.hide_card:
        return False
    game = room.current_game
    if CardReveal.objects.filter(player=player, game=game).exists():
        return False
    return not RevealedEvent.objects.filter(
        player__room=room, timestamp__gt=game.created_date).exists()


def fog_color_for(player):
    """The color whose view of a fog of war board the player's OBS source
    shows: a counter watches their monitored color, anyone else their own."""
    monitoring = player.monitoring_color
    return (monitoring or player.color).name


def resolve_target(user, anon_player):
    """The Player an OBS link shows: a user's link follows them between
    rooms; an anonymous player's link is tied to their one player and only
    works while that player is connected."""
    if user is not None:
        return obs_target(user)
    if anon_player is not None and anon_player.connected:
        return anon_player
    return None


def obs_state(user, anon_player=None):
    """What the OBS page shows, as a small dict the page polls for changes."""
    player = resolve_target(user, anon_player)
    if player is None:
        return {"room": None, "game": None, "hidden": False, "stars": [],
                "color": None}
    return {
        "room": player.room.encoded_uuid,
        "game": player.room.current_game.id,
        "hidden": board_hidden_for(player),
        "stars": starred_slots(player),
        "color": fog_color_for(player),
    }


def starred_slots(player):
    """The slots (1-based) `player` has starred on the room's current card."""
    from bingosync.models.rooms import StarredSquare
    return sorted(StarredSquare.objects.filter(
        player=player, game=player.room.current_game
    ).values_list("slot", flat=True))
