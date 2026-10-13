"""
reconcile_connections disconnects players the websocket server has no live
socket for. Connections live in the websocket server's memory, so after a
restart (every deploy) nobody's disconnect was reported; without this those
players stay "in the room" forever.
"""
import datetime
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from bingosync.models.rooms import Room, Game, Player
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.models.game_type import GameType
from bingosync.models.events import ConnectionEvent

LONG_AGO = timezone.now() - datetime.timedelta(minutes=10)


class ReconcileConnectionsTests(TestCase):

    def setUp(self):
        self.room = Room.objects.create(
            name="R", room_code="RECON1", passphrase="", hide_card=False,
            active=True)
        Game.from_board([{"name": f"G{i}", "tier": 0} for i in range(1, 26)],
                        room=self.room, seed=1,
                        game_type_value=GameType.hp_cos.value,
                        lockout_mode_value=1)
        self.live = self._player("live", connected_at=LONG_AGO)
        self.stale = self._player("stale", connected_at=LONG_AGO)
        self.never_opened_socket = self._player("never", created=LONG_AGO)
        self.just_joined = self._player("new")

    def _player(self, name, connected_at=None, created=None):
        player = Player.objects.create(
            room=self.room, name=name, role=Role.PLAYER,
            color_value=Color.red.value)
        if created:
            Player.objects.filter(pk=player.pk).update(created_date=created)
            player.refresh_from_db()
        if connected_at:
            event = ConnectionEvent.atomically_connect(player)
            ConnectionEvent.objects.filter(pk=event.pk).update(timestamp=connected_at)
        return player

    def _reconcile(self, live_uuids, secret=settings.INTERNAL_API_SECRET):
        response = MagicMock()
        response.json.return_value = {self.room.encoded_uuid: live_uuids}
        with patch("bingosync.views.requests.get", return_value=response), \
                patch("bingosync.views.publish_connection_event") as publish:
            result = self.client.get(
                "/api/reconcile", HTTP_X_INTERNAL_SECRET=secret)
        return result, publish

    def test_players_without_a_live_socket_are_disconnected(self):
        result, publish = self._reconcile([self.live.encoded_uuid])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), {"disconnected": 2})

        for player in (self.stale, self.never_opened_socket):
            player.refresh_from_db()
            self.assertFalse(player.connected, player.name)
        self.assertTrue(self.live.connected)
        # Everyone in the room is told, so player lists update
        self.assertEqual(publish.call_count, 2)

    def test_someone_who_just_joined_is_left_alone(self):
        # Their page may still be loading, so no socket yet
        self._reconcile([self.live.encoded_uuid])
        self.assertTrue(self.just_joined.connected)

    def test_disconnect_reported_twice_is_recorded_once(self):
        # The websocket server's grace-period report and a reconcile can
        # both arrive for the same player
        headers = {"HTTP_X_INTERNAL_SECRET": settings.INTERNAL_API_SECRET}
        with patch("bingosync.views.publish_connection_event") as publish:
            for _ in range(2):
                self.client.get(
                    f"/api/disconnected/{self.stale.encoded_uuid}", **headers)
        self.assertEqual(ConnectionEvent.objects.filter(
            player=self.stale, event=2).count(), 1)
        self.assertEqual(publish.call_count, 1)

    def test_requires_the_internal_secret(self):
        result, _ = self._reconcile([], secret="wrong")
        self.assertEqual(result.status_code, 401)
        self.stale.refresh_from_db()
        self.assertTrue(self.stale.connected)
