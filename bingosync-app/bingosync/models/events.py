from django.db import models, transaction
from django.utils import timezone

import datetime
from enum import Enum, unique

from bingosync.models.colors import Color
from bingosync.models.game_type import GameType


class Event(models.Model):
    player = models.ForeignKey("bingosync.Player", on_delete=models.CASCADE)
    timestamp = models.DateTimeField("Sent", default=timezone.now)
    player_color_value = models.IntegerField(choices=Color.player_choices())

    @property
    def player_color(self):
        return Color.for_value(self.player_color_value)

    @property
    def json_timestamp(self):
        return self.timestamp.replace().timestamp()

    @staticmethod
    def event_classes():
        return [
            ChatEvent,
            GoalEvent,
            ColorEvent,
            RevealedEvent,
            ConnectionEvent,
            NewCardEvent,
            RoleChangeEvent,
            CounterAssignmentEvent,
            ClaimReviewEvent]

    @staticmethod
    def get_all_for_room(room):
        all_events = []
        for event_class in Event.event_classes():
            all_events.extend(event_class.objects.filter(player__room=room))
        return sorted(all_events, key=lambda event: event.timestamp)

    @staticmethod
    def get_all_recent_for_room(room):
        recent_events = []
        total_events = 0
        for event_class in Event.event_classes():
            total_events += event_class.objects.filter(
                player__room=room).count()
            recent_events.extend(
                event_class.objects.filter(
                    player__room=room).filter(
                    timestamp__gte=datetime.datetime.now(
                        datetime.timezone.utc)
                    - datetime.timedelta(
                        hours=24)))
        all_included = total_events == len(recent_events)
        recent_events = sorted(
            recent_events,
            key=lambda event: event.timestamp)
        return {'events': recent_events, 'all_included': all_included}

    @staticmethod
    def get_latest_for_room(room):
        latest_events = []
        for event_class in Event.event_classes():
            try:
                latest_event = event_class.objects.filter(
                    player__room=room).latest()
                latest_events.append(latest_event)
            except event_class.DoesNotExist:
                pass
        if latest_events:
            return sorted(latest_events, key=lambda event: event.timestamp)[-1]
        else:
            return None

    class Meta:
        abstract = True
        get_latest_by = "timestamp"


class ChatEvent(Event):
    body = models.TextField()
    is_system_message = models.BooleanField(default=False)

    class Meta(Event.Meta):
        indexes = [models.Index(fields=['timestamp'])]

    def to_json(self):
        return {
            "type": "chat",
            "player": self.player.to_json(),
            "player_color": self.player_color.name,
            "text": self.body,
            "timestamp": self.json_timestamp,
            "is_system_message": self.is_system_message
        }


class NewCardEvent(Event):
    game_type_value = models.IntegerField(choices=GameType.choices())
    seed = models.BigIntegerField(default=0)
    hide_card = models.BooleanField(default=False)
    fog_of_war = models.BooleanField(default=False)

    class Meta(Event.Meta):
        indexes = [models.Index(fields=['timestamp'])]

    @property
    def game_type(self):
        return GameType.for_value(self.game_type_value)

    @property
    def is_current(self):
        new_card_events = NewCardEvent.objects.filter(
            player__room=self.player.room).order_by("timestamp")
        return new_card_events.last() == self

    def to_json(self):
        return {
            "type": "new-card",
            "player": self.player.to_json(),
            "player_color": self.player_color.name,
            "game": GameType.for_value(self.game_type_value).long_name,
            "seed": self.seed,
            "hide_card": self.hide_card,
            "is_current": self.is_current,
            "timestamp": self.json_timestamp,
            "fog_of_war": self.fog_of_war,
        }


class GoalEvent(Event):
    square = models.ForeignKey("bingosync.Square", on_delete=models.CASCADE)
    color_value = models.IntegerField(choices=Color.goal_choices())
    remove_color = models.BooleanField(default=False)
    claim_status = models.CharField(
        "Claim Status",
        max_length=20,
        default='confirmed',
        help_text="Status of the claim when event was created"
    )

    class Meta(Event.Meta):
        indexes = [models.Index(fields=['timestamp'])]

    @property
    def color(self):
        return Color.for_value(self.color_value)

    def to_json(self):
        return {
            "type": "goal",
            "player": self.player.to_json(),
            "square": self.square.to_json(),
            "player_color": self.player_color.name,
            "color": self.color.name,
            "remove": self.remove_color,
            "claim_status": self.claim_status,
            "timestamp": self.json_timestamp
        }


class ColorEvent(Event):
    color_value = models.IntegerField(choices=Color.player_choices())

    class Meta(Event.Meta):
        indexes = [models.Index(fields=['timestamp'])]

    @property
    def color(self):
        return Color.for_value(self.color_value)

    def to_json(self):
        return {
            "type": "color",
            "player": self.player.to_json(),
            "player_color": self.player_color.name,
            "color": self.color.name,
            "timestamp": self.json_timestamp
        }


class RevealedEvent(Event):

    class Meta(Event.Meta):
        indexes = [models.Index(fields=['timestamp'])]

    def to_json(self):
        return {
            "type": "revealed",
            "player": self.player.to_json(),
            "player_color": self.player_color.name,
            "timestamp": self.json_timestamp
        }


@unique
class ConnectionEventType(Enum):
    connected = 1
    disconnected = 2

    def __str__(self):
        return self.name.capitalize()

    @staticmethod
    def for_value(value):
        return list(ConnectionEventType)[value - 1]

    @staticmethod
    def choices():
        return [(event.value, str(event)) for event in ConnectionEventType]


class RoleChangeEvent(Event):
    """Event for tracking role changes in a room."""
    target_player = models.ForeignKey(
        "bingosync.Player",
        on_delete=models.CASCADE,
        related_name='role_change_targets')
    old_role = models.CharField(max_length=20)
    new_role = models.CharField(max_length=20)

    class Meta(Event.Meta):
        indexes = [models.Index(fields=['timestamp'])]

    def to_json(self):
        return {
            "type": "role_change",
            "player": self.player.to_json(),  # The gamemaster who made the change
            "player_color": self.player_color.name,
            "target_player": self.target_player.to_json(),
            "old_role": self.old_role,
            "new_role": self.new_role,
            "timestamp": self.json_timestamp
        }


class CounterAssignmentEvent(Event):
    """Event for tracking counter assignments to players."""
    counter_player = models.ForeignKey(
        "bingosync.Player",
        on_delete=models.CASCADE,
        related_name='counter_assignments_made')
    monitored_player = models.ForeignKey(
        "bingosync.Player",
        on_delete=models.CASCADE,
        related_name='counter_assignments_received',
        null=True,
        blank=True)  # Null means unassignment

    class Meta(Event.Meta):
        indexes = [models.Index(fields=['timestamp'])]

    def to_json(self):
        return {
            "type": "counter_assignment",
            "player": self.player.to_json(),  # The gamemaster or counter who made the assignment
            "player_color": self.player_color.name,
            "counter_player": self.counter_player.to_json(),
            "monitored_player": self.monitored_player.to_json() if self.monitored_player else None,
            "timestamp": self.json_timestamp
        }


class ClaimReviewEvent(Event):
    """Event for tracking counter claim reviews."""
    square = models.ForeignKey("bingosync.Square", on_delete=models.CASCADE)
    action = models.CharField(
        max_length=20,
        choices=[
            ('under_review', 'Under Review'),
            ('confirm', 'Confirm'),
            ('reject', 'Reject'),
        ],
        help_text="Action taken by counter: under_review, confirm, or reject"
    )
    reviewed_player = models.ForeignKey(
        "bingosync.Player",
        on_delete=models.CASCADE,
        related_name='claim_reviews_received',
        help_text="Player whose claim was reviewed"
    )

    class Meta(Event.Meta):
        indexes = [models.Index(fields=['timestamp'])]

    def to_json(self):
        return {
            "type": "claim_review",
            "player": self.player.to_json(),  # The counter who reviewed
            "player_color": self.player_color.name,
            "square": self.square.to_json(),
            "action": self.action,
            "reviewed_player": self.reviewed_player.to_json(),
            "timestamp": self.json_timestamp
        }


class ConnectionEvent(Event):
    event = models.IntegerField(choices=ConnectionEventType.choices())

    class Meta(Event.Meta):
        indexes = [models.Index(fields=['timestamp'])]

    @property
    def event_type(self):
        return ConnectionEventType.for_value(self.event)

    @staticmethod
    def make_connected_event(player):
        return ConnectionEvent(
            player=player,
            player_color_value=player.color.value,
            event=ConnectionEventType.connected.value)

    @staticmethod
    def atomically_connect(player):
        with transaction.atomic():
            connected_event = ConnectionEvent.make_connected_event(player)
            connected_event.save()
            player.room.update_active()
            return connected_event

    @staticmethod
    def make_disconnected_event(player):
        return ConnectionEvent(
            player=player,
            player_color_value=player.color.value,
            event=ConnectionEventType.disconnected.value)

    @staticmethod
    def atomically_disconnect(player):
        with transaction.atomic():
            disconnected_event = ConnectionEvent.make_disconnected_event(
                player)
            disconnected_event.save()
            player.room.update_active()
            return disconnected_event

    def to_json(self):
        return {
            "type": "connection",
            "event_type": self.event_type.name,
            "player": self.player.to_json(),
            "player_color": self.player_color.name,
            "timestamp": self.json_timestamp
        }
