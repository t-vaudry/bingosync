"""Resolving a user's permanent OBS link to the room and player it shows."""
from bingosync.models.events import RevealedEvent
from bingosync.models.rooms import CardReveal, Player


def obs_target(user):
    """The Player whose room the user's OBS link currently shows, or None.

    Among the rooms the user is connected to: the one they picked
    (`obs_room`), else their only one, else the one joined most recently.
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
    return players[0]


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


def resolve_target(user, anon_player):
    """The Player an OBS link shows: a user's link follows them between
    rooms; an anonymous player's link is tied to their one player."""
    return obs_target(user) if user is not None else anon_player


def obs_state(user, anon_player=None):
    """What the OBS page shows, as a small dict the page polls for changes."""
    player = resolve_target(user, anon_player)
    if player is None:
        return {"room": None, "game": None, "hidden": False}
    return {
        "room": player.room.encoded_uuid,
        "game": player.room.current_game.id,
        "hidden": board_hidden_for(player),
    }
