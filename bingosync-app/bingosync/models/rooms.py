from django.db import models, transaction
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

import datetime
from uuid import uuid4
from enum import Enum
import math
import urllib.parse

from bingosync.models.game_type import GameType
from bingosync.models.colors import Color, CompositeColor
from bingosync.models.events import (
    Event, GoalEvent, ColorEvent, RevealedEvent,
    ConnectionEventType, ConnectionEvent
)
from bingosync.models.enums import Role
from bingosync.util import ANON_UUID, encode_uuid, decode_uuid


STALE_THRESHOLD = datetime.timedelta(minutes=90)


class Room(models.Model):
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)
    name = models.CharField(max_length=255)
    room_code = models.CharField(max_length=8, unique=True, db_index=True, help_text="Short code for joining room")
    created_date = models.DateTimeField("Creation Time", default=timezone.now)
    passphrase = models.CharField(max_length=255)
    active = models.BooleanField("Active", default=False, db_index=True)
    hide_card = models.BooleanField("Initially Hide Card", default=False)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Room: id: {!r}, uuid: {!r}>".format(
            self.id, self.encoded_uuid)

    def get_absolute_url(self, with_password=False):
        from bingosync.views import room_view
        kwargs = {
            "encoded_room_uuid": self.encoded_uuid
        }
        result = reverse(room_view, kwargs=kwargs)
        if with_password:
            result += '?' + \
                urllib.parse.urlencode({'password': self.passphrase})
        return result

    @staticmethod
    def get_for_encoded_uuid(encoded_room_uuid):
        try:
            decoded_uuid = decode_uuid(encoded_room_uuid)
        except ValueError:
            raise Room.DoesNotExist(
                "Malformed encoded uuid: '"
                + str(encoded_room_uuid)
                + "'"
            )
        return Room.objects.get(uuid=decoded_uuid)

    @staticmethod
    def get_for_encoded_uuid_or_404(encoded_room_uuid):
        try:
            return Room.get_for_encoded_uuid(encoded_room_uuid)
        except Room.DoesNotExist:
            raise Http404

    @staticmethod
    def generate_room_code():
        """Generate a unique 6-character room code."""
        import random
        import string
        
        while True:
            # Generate 6-character code (uppercase letters and digits)
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            # Check if code already exists
            if not Room.objects.filter(room_code=code).exists():
                return code

    @staticmethod
    def get_for_room_code(room_code):
        """Get room by room code."""
        try:
            return Room.objects.get(room_code=room_code.upper())
        except Room.DoesNotExist:
            raise Room.DoesNotExist(f"Room with code '{room_code}' not found")

    @staticmethod
    def get_for_room_code_or_404(room_code):
        """Get room by room code or raise 404."""
        try:
            return Room.get_for_room_code(room_code)
        except Room.DoesNotExist:
            raise Http404

    @staticmethod
    def get_with_multiple_players():
        return Room.objects.annotate(
            num_players=models.Count('player')).filter(
            num_players__gt=1)

    @property
    def encoded_uuid(self):
        return encode_uuid(self.uuid)

    @property
    def current_game(self):
        return Game.objects.filter(room=self).order_by("-created_date").first()

    @property
    def games(self):
        return Game.objects.filter(room=self).order_by("created_date").all()

    @property
    def players(self):
        return Player.objects.filter(room=self).order_by("name")

    @property
    def connected_players(self):
        return [player for player in self.players if player.connected]

    @property
    def connected_spectators(self):
        return [player for player in self.connected_players if player.is_spectator]

    @property
    def latest_event_timestamp(self):
        latest_event = Event.get_latest_for_room(self)
        return latest_event.timestamp if latest_event else self.created_date

    @property
    def is_idle(self):
        idle_time = datetime.datetime.now(
            datetime.timezone.utc) - self.latest_event_timestamp
        return idle_time > STALE_THRESHOLD

    @property
    def is_seed_hidden(self):
        if not self.hide_card:
            return False
        latest_game_start = self.current_game.created_date
        latest_revealed_event = RevealedEvent.objects.filter(
            player__room=self).order_by("timestamp").last()
        return not latest_revealed_event or latest_game_start >= latest_revealed_event.timestamp

    def update_active(self):
        """
        Update room active status.

        A room is active if it has at least one connected non-spectator
        (gamemaster, player, or counter). Spectators alone don't keep a room active.

        When a room becomes inactive, all remaining spectators are disconnected.
        """
        non_spectator_players = [
            player for player in self.connected_players 
            if not player.is_spectator
        ]
        was_active = self.active
        self.active = len(non_spectator_players) > 0

        self.save()

        # If room just became inactive, disconnect all remaining spectators
        if was_active and not self.active:
            from bingosync.models.events import ConnectionEvent
            from bingosync.publish import publish_connection_event

            for spectator in self.connected_spectators:
                # Create and publish disconnect event for each spectator
                disconnected_event = ConnectionEvent.make_disconnected_event(spectator)
                disconnected_event.save()
                publish_connection_event(disconnected_event)

                # Clear current_room for authenticated spectators to allow joining other rooms
                if spectator.user and spectator.user.current_room == self:
                    spectator.user.current_room = None
                    spectator.user.save()

    @property
    def creator(self):
        return self.players.order_by("created_date").first()

    @property
    def settings(self):
        game = self.current_game
        return {
            "hide_card": self.hide_card,
            "lockout_mode": str(game.lockout_mode),
            "fog_of_war": game.fog_of_war,
            "game": str(game.game_type.group),
            "game_id": game.game_type.group.value,
            "variant": str(game.game_type),
            "variant_id": game.game_type_value,
            "seed": game.seed,
        }

    def players_with_color(self, color):
        """Connected players (Player role) currently using `color`."""
        return [player for player in self.connected_players
                if player.role == Role.PLAYER and player.color == color]

    def color_label(self, color):
        """How to name a color: its player's name when exactly one connected
        player uses it, otherwise the color's name."""
        players = self.players_with_color(color)
        return players[0].name if len(players) == 1 else color.name

    @property
    def has_gamemaster(self):
        return Player.objects.filter(room=self, role=Role.GAMEMASTER).exists()

    def seed_visible_to(self, player):
        """Whether `player` may see the seed.

        In a room run by a Gamemaster, only the Gamemaster and counters see it;
        players, spectators and anonymous viewers (stream overlay, Room
        History) don't. Without a Gamemaster everyone does.
        """
        if not self.has_gamemaster:
            return True
        return player is not None and player.role in (
            Role.GAMEMASTER, Role.COUNTER)

    def settings_for(self, player, settings=None):
        """Room settings as `player` may see them (seed removed if hidden).

        `settings` lets callers pass an already-fetched (e.g. cached) copy.
        """
        settings = dict(self.settings if settings is None else settings)
        if not self.seed_visible_to(player):
            settings["seed"] = None
        return settings


class LockoutMode(Enum):
    non_lockout = 1
    lockout = 2

    def __str__(self):
        return LOCKOUT_MODE_NAMES[self]

    @staticmethod
    def for_value(value):
        return list(LockoutMode)[value - 1]

    @staticmethod
    def default_value():
        return LockoutMode.non_lockout.value

    @staticmethod
    def choices():
        return [(lockout_mode.value, str(lockout_mode))
                for lockout_mode in LockoutMode]


LOCKOUT_MODE_NAMES = {
    LockoutMode.non_lockout: "Non-Lockout",
    LockoutMode.lockout: "Lockout",
}


class Game(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    seed = models.BigIntegerField()
    size = models.IntegerField()
    created_date = models.DateTimeField("Creation Time", default=timezone.now)
    game_type_value = models.IntegerField(
        "Game Type",
        choices=GameType.choices(),
        default=50)  # Default to HP CoS
    lockout_mode_value = models.IntegerField(
        "Lockout Mode",
        choices=LockoutMode.choices(),
        default=LockoutMode.default_value())
    fog_of_war = models.BooleanField("Fog of War", default=False)
    winner = models.ForeignKey(
        'Player',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_games',
        help_text="Player who won this lockout game (first to a majority of "
                  "confirmed squares); null while the game is unwon")

    def __str__(self):
        return self.room.name + ": " + str(self.seed)

    @staticmethod
    def from_board(board_json, *args, **kwargs):
        size = int(math.sqrt(len(board_json)))
        assert size * size == len(board_json)
        kwargs['size'] = size
        with transaction.atomic():
            game = Game(*args, **kwargs)
            game.full_clean()
            game.save()
            for index, square_json in enumerate(board_json):
                slot = index + 1

                # hack to make tier work with non-SRL formats
                tier = square_json.get("tier")
                if tier is None:
                    tier = -1
                square = Square(
                    game=game,
                    slot=slot,
                    goal=square_json["name"],
                    tier=tier,
                    goal_key=square_json.get("goal_key", ""),
                    amount=square_json.get("amount", 1),
                    unique_amount=square_json.get(
                        "unique_amount", square_json.get("amount", 1)),
                    triggers=square_json.get("triggers", []))

                square.full_clean()
                square.save()
        return game

    @property
    def game_type(self):
        return GameType.for_value(self.game_type_value)

    @property
    def lockout_mode(self):
        return LockoutMode.for_value(self.lockout_mode_value)

    @property
    def squares(self):
        return Square.objects.filter(game=self).order_by("slot")

    @property
    def board(self):
        return [square.to_json() for square in self.squares]

    def update_goal(self, player, slot, color, remove_color, claim_status='confirmed',
                    claimed_by=None):
        """Mark (or unmark) `color` on a square. `player` is whoever clicked;
        `claimed_by` is who the mark is credited to, when that's someone
        else (a counter marking for the player they count)."""
        square = self.squares[slot - 1]
        square_color = square.color

        # if we're in a lockout mode, verify that the color change is valid
        if self.lockout_mode == LockoutMode.lockout:
            # if we're trying to set a color and the square isn't blank, fail
            if not remove_color and square_color.colors != [Color.blank]:
                return False
            # if we're trying to clear a color and it's not our color, fail
            if remove_color and square_color.colors != [color]:
                return False

        if remove_color:
            square_color.remove(color)
            # Other colors left on the square (non-lockout) still count
            remaining = [c for c in square_color.colors if c != Color.blank]
            square.claim_status = 'confirmed' if remaining else 'none'
            if not remaining or (square.claimed_by is not None
                                 and square.claimed_by.color == color):
                square.claimed_by = None
            square.reviewed_by = None
        else:
            square_color.add(color)
            # Set claim status and claimed_by
            square.claim_status = claim_status
            square.claimed_by = claimed_by or player
        
        square.color = square_color
        square.save()

        goal_event = GoalEvent(
            player=player,
            square=square,
            color_value=color.value,
            player_color_value=player.color.value,
            remove_color=remove_color,
            claim_status=square.claim_status)
        goal_event.save()
        return goal_event


SLOT_RANGE = range(1, 26)
SLOT_CHOICES = [(num, str(num)) for num in SLOT_RANGE]


def validate_in_slot_range(slot):
    return slot in SLOT_RANGE


# Claim statuses that count toward score, bingos and a lockout win. Marks are
# approved by default; a counter putting one in review doesn't stop it
# counting. Only unmarking it does ('rejected' is from the old review flow).
COUNTED_CLAIM_STATUSES = ('confirmed', 'under_review')


class Square(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    slot = models.IntegerField()
    goal = models.CharField(max_length=255)
    tier = models.IntegerField(default=0)
    color_value = models.IntegerField(
        "Color",
        default=CompositeColor.goal_default().value,
        choices=CompositeColor.goal_choices())

    # Claim review system fields
    claim_status = models.CharField(
        "Claim Status",
        max_length=20,
        default='none',
        choices=[
            ('none', 'None'),
            ('under_review', 'Under Review'),
            ('confirmed', 'Confirmed'),
            ('rejected', 'Rejected'),
        ],
        help_text="Status of the claim for counter review system"
    )
    claimed_by = models.ForeignKey(
        'Player',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='claimed_squares',
        help_text="Player who claimed this square"
    )
    reviewed_by = models.ForeignKey(
        'Player',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_squares',
        help_text="Counter who reviewed this claim"
    )

    # What a counter needs to count the goal (from the generator). Only sent
    # to counters (see CounterTally); the board JSON leaves them out.
    goal_key = models.CharField(
        max_length=100, blank=True, default='',
        help_text="The goal's id in the goal list; other goals' triggers "
                  "name it")
    amount = models.PositiveSmallIntegerField(
        default=1, help_text="How many it takes to complete the goal")
    unique_amount = models.PositiveSmallIntegerField(
        default=1, help_text="The most that linked goals can add to its count")
    triggers = models.JSONField(
        default=list, blank=True,
        help_text="Goal keys whose count goes up and down with this goal's")

    @property
    def is_counted(self):
        """Whether a counter counts this goal: it takes more than one step,
        or counting it also counts other goals."""
        return self.amount > 1 or bool(self.triggers)

    @property
    def color(self):
        return CompositeColor.for_value(self.color_value)

    @color.setter
    def color(self, color):
        self.color_value = color.value

    @property
    def slot_name(self):
        return "slot" + str(self.slot)

    def to_json(self):
        return {
            "name": self.goal,
            "tier": self.tier,
            "slot": self.slot_name,
            "colors": self.color.name,
            "claim_status": self.claim_status,
            "claimed_by": self.claimed_by.encoded_uuid if self.claimed_by else None,
            "reviewed_by": self.reviewed_by.encoded_uuid if self.reviewed_by else None,
        }

    class Meta:
        unique_together = (("game", "slot"),)
        indexes = [
            models.Index(fields=['game', 'slot']),
        ]



class Player(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid4, editable=False, unique=True)
    name = models.CharField(max_length=50)
    color_value = models.IntegerField(
        "Color",
        default=Color.player_default().value,
        choices=Color.player_choices())
    created_date = models.DateTimeField("Creation Time", default=timezone.now)

    # User link (nullable for anonymous spectators)
    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='player_sessions',
        help_text='Linked user account (null for anonymous spectators)'
    )

    # Role system fields
    role = models.CharField(
        "Role",
        max_length=20,
        choices=Role.choices,
        default=Role.PLAYER
    )
    # Colors claim squares; players are associated with a color. A counter
    # reviews a color's goals, whoever marked them.
    monitoring_color_value = models.IntegerField(
        null=True,
        blank=True,
        choices=Color.goal_choices(),
        help_text="For Counter role: the color being counted"
    )

    class Meta:
        indexes = [models.Index(fields=['room', 'user'])]

    @staticmethod
    def get_for_encoded_uuid(encoded_player_uuid):
        decoded_uuid = decode_uuid(encoded_player_uuid)
        if decoded_uuid == ANON_UUID:
            return ANON_PLAYER
        return Player.objects.get(uuid=decoded_uuid)

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<Player: id: {!r}, uuid: {!r}, name: {!r}>".format(
            self.id, self.encoded_uuid, self.name)

    @property
    def encoded_uuid(self):
        return encode_uuid(self.uuid)

    @property
    def is_spectator(self):
        """Derived property: True if role is SPECTATOR."""
        return self.role == Role.SPECTATOR

    @property
    def color(self):
        if self.is_spectator:
            return Color.blank
        return Color.for_value(self.color_value)

    @property
    def connected(self):
        last_connection_event = (
            ConnectionEvent.objects.filter(player=self)
            .order_by("timestamp").last()
        )
        return (
            not last_connection_event
            or last_connection_event.event_type == ConnectionEventType.connected
        )

    def update_color(self, color):
        with transaction.atomic():
            color_event = ColorEvent(
                player=self,
                player_color_value=self.color.value,
                color_value=color.value)
            color_event.save()
            self.color_value = color.value
            self.save()
        return color_event

    @property
    def monitoring_color(self):
        """The color a counter is counting, or None."""
        if not self.monitoring_color_value:
            return None
        return Color.for_value(self.monitoring_color_value)

    def to_json(self):
        monitoring_color = self.monitoring_color
        return {
            "uuid": self.encoded_uuid,
            "name": self.name,
            "color": self.color.name,
            "is_spectator": self.is_spectator,
            "role": self.role,
            "monitoring_color": monitoring_color.name if monitoring_color else None,
            "is_logged_in": self.user is not None
        }


ANON_PLAYER = Player(uuid=ANON_UUID, name="Anonymous", role=Role.SPECTATOR)


class CompletedLine(models.Model):
    """A line (row, column, or diagonal) a player has completed in a game.

    One row per (game, player, line); the unique constraint makes crediting a
    line idempotent so a bingo counts exactly once. `line` is a stable key
    like "row-0", "col-3", "diag-main", "diag-anti".
    """
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name='completed_lines')
    player = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name='completed_lines')
    line = models.CharField(max_length=16)
    created_date = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = (("game", "player", "line"),)


class CounterTally(models.Model):
    """A counter's goal counts for one color in a game ("3/6 Gnomes").

    Private to that counter: two counters on one color keep separate tallies
    (they count independently to verify each other), and nothing here goes to
    the room. `counts` and `saved_counts` map a slot ("7") to its count;
    `saved_counts` is the snapshot Load goes back to when the runner loses
    in-game progress (fainting, reloading a save book). `dismissed` lists
    slots whose "marked before counted" alert the counter has dismissed for
    the current mark.
    """
    game = models.ForeignKey(
        Game, on_delete=models.CASCADE, related_name='counter_tallies')
    counter = models.ForeignKey(
        Player, on_delete=models.CASCADE, related_name='counter_tallies')
    color_value = models.IntegerField(choices=Color.goal_choices())
    counts = models.JSONField(default=dict, blank=True)
    saved_counts = models.JSONField(null=True, blank=True)
    saved_at = models.DateTimeField(null=True, blank=True)
    dismissed = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = (("game", "counter", "color_value"),)

    class Invalid(Exception):
        pass

    @staticmethod
    def for_update(game, counter, color):
        """The tally, locked for the rest of the transaction."""
        CounterTally.objects.get_or_create(
            game=game, counter=counter, color_value=color.value)
        return CounterTally.objects.select_for_update().get(
            game=game, counter=counter, color_value=color.value)

    def count(self, slot):
        return self.counts.get(str(slot), 0)

    def change(self, squares, slot, delta):
        """Count one more (delta 1) or one fewer (delta -1) of a goal. Goals
        it triggers move with it, each staying between 0 and its unique
        amount; a linked goal already at its limit is left alone."""
        if delta not in (1, -1):
            raise CounterTally.Invalid("Count up or down by one.")
        square = self._counted_square(squares, slot)
        new_count = self.count(slot) + delta
        if not 0 <= new_count <= square.amount:
            raise CounterTally.Invalid(
                "That goal is already at {}.".format(self.count(slot)))
        self.counts[str(slot)] = new_count
        for linked in squares:
            if linked.slot == slot or not linked.goal_key:
                continue
            if linked.goal_key in square.triggers:
                linked_count = self.count(linked.slot) + delta
                if 0 <= linked_count <= linked.unique_amount:
                    self.counts[str(linked.slot)] = linked_count

    def save_state(self):
        self.saved_counts = dict(self.counts)
        self.saved_at = timezone.now()

    def load_state(self):
        """Go back to the saved counts. Dismissed alerts come back for goals
        that are still short."""
        if self.saved_counts is None:
            raise CounterTally.Invalid("Nothing is saved.")
        self.counts = dict(self.saved_counts)
        self.dismissed = []

    def clear_saved(self):
        self.saved_counts = None
        self.saved_at = None

    def reset(self):
        self.counts = {}
        self.dismissed = []
        self.clear_saved()

    def dismiss(self, squares, slot):
        self._counted_square(squares, slot)
        if slot not in self.dismissed:
            self.dismissed.append(slot)

    def _counted_square(self, squares, slot):
        for square in squares:
            if square.slot == slot:
                if not square.is_counted:
                    raise CounterTally.Invalid("That goal isn't counted.")
                return square
        raise CounterTally.Invalid("Invalid slot: {}".format(slot))

    @staticmethod
    def forget_dismissal(game, color, slot):
        """A color came off a square: a later mark there alerts again."""
        for tally in CounterTally.objects.filter(
                game=game, color_value=color.value):
            if slot in tally.dismissed:
                tally.dismissed.remove(slot)
                tally.save(update_fields=["dismissed"])

    def to_json(self, squares):
        return {
            "color": Color.for_value(self.color_value).name,
            "goals": {
                str(square.slot): {
                    "amount": square.amount,
                    "unique_amount": square.unique_amount,
                } for square in squares if square.is_counted
            },
            "counts": self.counts,
            "saved_at": self.saved_at.isoformat() if self.saved_at else None,
            "dismissed": self.dismissed,
        }
