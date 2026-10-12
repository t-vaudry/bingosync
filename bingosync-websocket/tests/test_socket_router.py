"""
Tests for SocketRouter bookkeeping: a closing socket must be removed (and the
player's disconnect posted) immediately, wherever its room sits in the
router, and looking up a room must not create entries.
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

    def test_leaving_player_is_disconnected_despite_empty_rooms(
            self, post_connect, post_disconnect):
        # Rooms with nobody connected (e.g. ones that received a broadcast)
        # sit ahead of the leaving player's room.
        self.router.send_to_room("empty-1", "msg")
        self.router.sockets_by_room["empty-2"]
        ws = FakeSocket()
        self.router.register("room", "player", ws)

        self.router.unregister(ws)

        post_disconnect.assert_called_once_with("player")
        self.assertNotIn(ws, list(self.router.all_sockets))

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
        post_disconnect.assert_not_called()

        self.router.unregister(second)
        post_disconnect.assert_called_once_with("player")
        self.assertEqual(list(self.router.all_sockets), [])

    def test_other_players_in_room_are_unaffected(
            self, post_connect, post_disconnect):
        leaving, staying = FakeSocket(), FakeSocket()
        self.router.register("room", "leaver", leaving)
        self.router.register("room", "stayer", staying)

        self.router.unregister(leaving)

        post_disconnect.assert_called_once_with("leaver")
        self.assertEqual(list(self.router.all_sockets), [staying])
        self.router.send_to_room("room", "msg")
        self.assertEqual(staying.sent, ["msg"])

    def test_unregistering_unknown_socket_does_nothing(
            self, post_connect, post_disconnect):
        self.router.register("room", "player", FakeSocket())
        self.router.unregister(FakeSocket())
        post_disconnect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
