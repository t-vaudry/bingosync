"""
The players panel has to match the room at all times. The page renders it
once and then follows socket events, so the server needs to be able to say
who is in the room (room_players), and the connection records behind that
have to stay true: spectators and commentators aren't dropped when a room
goes quiet, a stale disconnect doesn't remove someone whose page is live, and
reconcile puts right a live socket whose player is marked disconnected.
"""
import datetime
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from bingosync.models.colors import Color
from bingosync.models.enums import Role
from bingosync.models.events import ConnectionEvent
from bingosync.models.game_type import GameType
from bingosync.models.rooms import Game, Player, Room

User = get_user_model()
LONG_AGO = timezone.now() - datetime.timedelta(minutes=10)
# Later than the connect, but still long enough ago to be past reconcile's grace
LONG_AGO_DISCONNECT = LONG_AGO + datetime.timedelta(minutes=1)
SECRET = {"HTTP_X_INTERNAL_SECRET": settings.INTERNAL_API_SECRET}


class PlayersPanelSyncTest(TestCase):

    def setUp(self):
        self.room = Room.objects.create(
            name="R", room_code="SYNC01", passphrase="", hide_card=False,
            active=True)
        Game.from_board([{"name": f"G{i}", "tier": 0} for i in range(1, 26)],
                        room=self.room, seed=1,
                        game_type_value=GameType.hp_cos.value,
                        lockout_mode_value=1)
        self.gm = self._join("gm", Role.GAMEMASTER, Color.red)
        self.ann = self._join("ann", Role.PLAYER, Color.blue)
        self.counter = self._join("counter", Role.COUNTER, Color.blue,
                                  monitoring=Color.blue)
        self.spectator = self._join("sam", Role.SPECTATOR, Color.blank)
        self.commentator = self._join("cass", Role.COMMENTATOR, Color.blank)

    def _join(self, name, role, color, monitoring=None, connected=True):
        user = User.objects.create_user(
            username=name, email=f"{name}@test.com", password="pw12345678")
        player = Player.objects.create(
            room=self.room, user=user, name=name, role=role,
            color_value=color.value,
            monitoring_color_value=monitoring.value if monitoring else None)
        if connected:
            event = ConnectionEvent.atomically_connect(player)
            ConnectionEvent.objects.filter(pk=event.pk).update(
                timestamp=LONG_AGO)
        return player

    def _players(self, viewer):
        client = Client()
        client.force_login(viewer.user)
        session = client.session
        session["authorized_rooms"] = {
            self.room.encoded_uuid: viewer.encoded_uuid}
        session.save()
        return client.get(f"/room/{self.room.encoded_uuid}/players")

    def _disconnect(self, player):
        event = ConnectionEvent.atomically_disconnect(player)
        ConnectionEvent.objects.filter(pk=event.pk).update(timestamp=LONG_AGO_DISCONNECT)

    # room_players

    def test_lists_everyone_connected_with_role_color_and_counting(self):
        result = self._players(self.gm)
        self.assertEqual(result.status_code, 200)
        by_name = {p["name"]: p for p in result.json()["players"]}
        self.assertEqual(set(by_name),
                         {"gm", "ann", "counter", "sam", "cass"})
        self.assertEqual(by_name["ann"]["role"], Role.PLAYER)
        self.assertEqual(by_name["ann"]["color"], Color.blue.name)
        self.assertEqual(by_name["counter"]["role"], Role.COUNTER)
        self.assertEqual(by_name["counter"]["monitoring_color"],
                         Color.blue.name)
        self.assertEqual(by_name["sam"]["role"], Role.SPECTATOR)
        self.assertEqual(by_name["cass"]["role"], Role.COMMENTATOR)
        self.assertEqual(result["Cache-Control"], "no-store")

    def test_a_disconnected_player_is_left_out(self):
        self._disconnect(self.ann)
        names = {p["name"] for p in self._players(self.gm).json()["players"]}
        self.assertNotIn("ann", names)

    def test_a_role_change_shows_at_once(self):
        self.ann.role = Role.SPECTATOR
        self.ann.save()
        by_name = {p["name"]: p
                   for p in self._players(self.gm).json()["players"]}
        self.assertEqual(by_name["ann"]["role"], Role.SPECTATOR)

    def test_a_counters_label_is_its_players_name_when_there_is_one(self):
        by_name = {p["name"]: p
                   for p in self._players(self.gm).json()["players"]}
        self.assertEqual(by_name["counter"]["monitored_label"], "ann")

    def test_a_counters_label_is_the_color_when_shared(self):
        self._join("bob", Role.PLAYER, Color.blue)
        by_name = {p["name"]: p
                   for p in self._players(self.gm).json()["players"]}
        self.assertEqual(by_name["counter"]["monitored_label"],
                         Color.blue.name)

    def test_the_label_follows_a_color_change(self):
        self.ann.color_value = Color.green.value
        self.ann.save()
        by_name = {p["name"]: p
                   for p in self._players(self.gm).json()["players"]}
        # Nobody is blue any more, so the label falls back to the color
        self.assertEqual(by_name["counter"]["monitored_label"],
                         Color.blue.name)

    def test_a_removed_player_is_refused_not_an_error(self):
        # Their session still points at a player row that is gone (kicked);
        # the page must get a clear "not in this room", not a server error
        client = Client()
        client.force_login(self.ann.user)
        session = client.session
        session["authorized_rooms"] = {
            self.room.encoded_uuid: self.ann.encoded_uuid}
        session.save()
        self.ann.delete()
        for path in (f"/room/{self.room.encoded_uuid}/players",
                     f"/api/get-socket-key/{self.room.encoded_uuid}"):
            self.assertEqual(client.get(path).status_code, 403, path)

    def test_only_people_in_the_room_may_ask(self):
        result = Client().get(f"/room/{self.room.encoded_uuid}/players")
        self.assertEqual(result.status_code, 403)

    # A quiet room keeps its watchers

    def test_a_room_going_inactive_keeps_its_spectators_and_commentators(self):
        for player in (self.gm, self.ann, self.counter):
            self._disconnect(player)
        with patch("bingosync.views.publish_connection_event"):
            self.room.update_active()
        self.assertFalse(Room.objects.get(pk=self.room.pk).active)
        self.spectator.refresh_from_db()
        self.commentator.refresh_from_db()
        self.assertTrue(self.spectator.connected)
        self.assertTrue(self.commentator.connected)

    # A stale disconnect

    def _sockets(self, live):
        response = MagicMock()
        response.json.return_value = {self.room.encoded_uuid: live}
        return patch("bingosync.views.requests.get", return_value=response)

    def test_a_disconnect_for_a_player_with_a_live_socket_is_ignored(self):
        with self._sockets([self.ann.encoded_uuid]), \
                patch("bingosync.views.publish_connection_event") as publish:
            Client().get(
                f"/api/disconnected/{self.ann.encoded_uuid}", **SECRET)
        self.assertTrue(self.ann.connected)
        publish.assert_not_called()

    def test_a_disconnect_for_a_player_without_a_socket_goes_through(self):
        with self._sockets([]), \
                patch("bingosync.views.publish_connection_event") as publish:
            Client().get(
                f"/api/disconnected/{self.ann.encoded_uuid}", **SECRET)
        self.assertFalse(self.ann.connected)
        self.assertEqual(publish.call_count, 1)

    def test_a_disconnect_goes_through_when_sockets_cant_be_asked(self):
        import requests
        with patch("bingosync.views.requests.get",
                   side_effect=requests.exceptions.ConnectionError()), \
                patch("bingosync.views.publish_connection_event"):
            Client().get(
                f"/api/disconnected/{self.ann.encoded_uuid}", **SECRET)
        self.assertFalse(self.ann.connected)

    # Reconcile repairs a live socket marked disconnected

    def _reconcile(self, live):
        with self._sockets(live), \
                patch("bingosync.views.publish_connection_event") as publish:
            result = Client().get("/api/reconcile", **SECRET)
        return result, publish

    def test_reconcile_reconnects_a_live_player_marked_disconnected(self):
        self._disconnect(self.spectator)
        live = [p.encoded_uuid for p in
                (self.gm, self.ann, self.counter, self.spectator,
                 self.commentator)]
        result, publish = self._reconcile(live)
        self.assertEqual(result.json(),
                         {"disconnected": 0, "reconnected": 1})
        self.assertTrue(self.spectator.connected)
        # Everyone is told, so their lists get the person back
        self.assertEqual(publish.call_count, 1)

    def test_reconcile_leaves_someone_who_just_left_alone(self):
        event = ConnectionEvent.atomically_disconnect(self.spectator)
        live = [self.spectator.encoded_uuid]
        result, _ = self._reconcile(live)
        self.assertEqual(result.json()["reconnected"], 0)
        self.assertFalse(self.spectator.connected)
        self.assertIsNotNone(event)

    def test_reconcile_covers_an_inactive_room_with_watchers(self):
        for player in (self.gm, self.ann, self.counter):
            self._disconnect(player)
        self._disconnect(self.spectator)
        Room.objects.filter(pk=self.room.pk).update(active=False)
        result, _ = self._reconcile([self.spectator.encoded_uuid])
        self.assertEqual(result.json()["reconnected"], 1)
        self.assertTrue(self.spectator.connected)
