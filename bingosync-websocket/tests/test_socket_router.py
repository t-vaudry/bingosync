"""
Tests for SocketRouter bookkeeping: a closing socket must be removed wherever
its room sits in the router, looking up a room must not create entries, and
a player is reported disconnected only if they haven't reconnected within the
grace period (so reloading the page isn't a disconnect).
"""

import os
import sys
import unittest
from unittest.mock import patch

# Add parent directory to path to import app module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as tornado_app  # noqa: E402


class FakeSocket:
    def __init__(self):
        self.sent = []

    def send(self, message):
        self.sent.append(message)


@patch.object(tornado_app, "post_player_disconnection")
@patch.object(tornado_app, "post_player_connection")
class SocketRouterTestCase(unittest.TestCase):

    def setUp(self):
        self.router = tornado_app.SocketRouter()
        # Keep test output readable
        log_patch = patch.object(tornado_app.SocketRouter, "log_sockets")
        log_patch.start()
        self.addCleanup(log_patch.stop)

        # Fake scheduler: collect delayed callbacks so a test can run them
        # ("let the grace period pass") when it chooses.
        self.scheduled = {}

        def call_later(delay, callback):
            handle = object()
            self.scheduled[handle] = (delay, callback)
            return handle

        self.router._call_later = call_later
        self.router._cancel = lambda handle: self.scheduled.pop(handle, None)

    def _let_grace_period_pass(self):
        for handle, (delay, callback) in list(self.scheduled.items()):
            self.assertEqual(delay, tornado_app.DISCONNECT_GRACE_SECONDS)
            del self.scheduled[handle]
            callback()

    def test_leaving_player_is_disconnected_despite_empty_rooms(
            self, post_connect, post_disconnect):
        # Rooms with nobody connected (e.g. ones that received a broadcast)
        # sit ahead of the leaving player's room.
        self.router.send_to_room("empty-1", "msg")
        self.router.sockets_by_room["empty-2"]
        ws = FakeSocket()
        self.router.register("room", "player", ws)

        self.router.unregister(ws)
        self.assertNotIn(ws, list(self.router.all_sockets))

        self._let_grace_period_pass()
        post_disconnect.assert_called_once_with("player")

    def test_disconnect_waits_for_the_grace_period(
            self, post_connect, post_disconnect):
        ws = FakeSocket()
        self.router.register("room", "player", ws)
        self.router.unregister(ws)

        post_disconnect.assert_not_called()
        self._let_grace_period_pass()
        post_disconnect.assert_called_once_with("player")

    def test_reloading_the_page_is_not_a_disconnect(
            self, post_connect, post_disconnect):
        old_page, new_page = FakeSocket(), FakeSocket()
        self.router.register("room", "player", old_page)

        self.router.unregister(old_page)          # old page unloads
        self.router.register("room", "player", new_page)  # new page connects
        self._let_grace_period_pass()

        post_disconnect.assert_not_called()
        post_connect.assert_called_once_with("player")  # no second "connected"
        self.assertEqual(list(self.router.all_sockets), [new_page])

    def test_connected_list_includes_players_reloading_the_page(
            self, post_connect, post_disconnect):
        # Django's reconcile disconnects anyone missing from this list, so a
        # player inside the grace period must still be on it.
        staying, reloading = FakeSocket(), FakeSocket()
        self.router.register("room", "stayer", staying)
        self.router.register("room", "reloader", reloading)
        self.router.unregister(reloading)

        self.assertEqual(self.router.connected_players_by_room(),
                         {"room": ["reloader", "stayer"]})

        self._let_grace_period_pass()
        self.assertEqual(self.router.connected_players_by_room(),
                         {"room": ["stayer"]})

    def test_broadcast_to_room_without_sockets_creates_no_entry(
            self, post_connect, post_disconnect):
        self.router.send_to_room("nobody-here", "msg")
        self.assertNotIn("nobody-here", self.router.sockets_by_room)

    def test_player_with_another_open_socket_stays_connected(
            self, post_connect, post_disconnect):
        first, second = FakeSocket(), FakeSocket()
        self.router.register("room", "player", first)
        self.router.register("room", "player", second)
        post_connect.assert_called_once_with("player")

        self.router.unregister(first)
        self._let_grace_period_pass()
        post_disconnect.assert_not_called()

        self.router.unregister(second)
        self._let_grace_period_pass()
        post_disconnect.assert_called_once_with("player")
        self.assertEqual(list(self.router.all_sockets), [])

    def test_other_players_in_room_are_unaffected(
            self, post_connect, post_disconnect):
        leaving, staying = FakeSocket(), FakeSocket()
        self.router.register("room", "leaver", leaving)
        self.router.register("room", "stayer", staying)

        self.router.unregister(leaving)
        self._let_grace_period_pass()

        post_disconnect.assert_called_once_with("leaver")
        self.assertEqual(list(self.router.all_sockets), [staying])
        self.router.send_to_room("room", "msg")
        self.assertEqual(staying.sent, ["msg"])

    def test_unregistering_unknown_socket_does_nothing(
            self, post_connect, post_disconnect):
        self.router.register("room", "player", FakeSocket())
        self.router.unregister(FakeSocket())
        self._let_grace_period_pass()
        post_disconnect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
