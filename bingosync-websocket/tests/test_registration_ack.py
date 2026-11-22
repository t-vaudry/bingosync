"""
A page that opens a socket is told once it is registered for the room's
events. Until then anything broadcast is missed, so the page re-reads the
state it could have missed (the players list, after a reconnect the board)
when it gets this message rather than guessing when the socket is ready.
"""
import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import app as tornado_app  # noqa: E402


class RegistrationAckTestCase(unittest.TestCase):

    def setUp(self):
        self.ws = tornado_app.BroadcastWebSocket(
            application=MagicMock(), request=MagicMock())
        self.ws.request.remote_ip = '192.168.1.1'
        self.sent = []
        self.ws.send = self.sent.append

    def test_a_registered_socket_is_told_so(self):
        with patch.object(tornado_app, 'load_player_data',
                          return_value=('room', 'player')), \
                patch.object(tornado_app.ROUTER, 'register') as register:
            self.ws.on_message(json.dumps({'socket_key': 'key'}))
        register.assert_called_once_with('room', 'player', self.ws)
        self.assertEqual([json.loads(m) for m in self.sent],
                         [{'type': 'registered'}])

    def test_a_refused_socket_gets_an_error_and_no_ack(self):
        with patch.object(tornado_app, 'load_player_data',
                          side_effect=ValueError('bad key')):
            self.ws.on_message(json.dumps({'socket_key': 'key'}))
        types = [json.loads(m)['type'] for m in self.sent]
        self.assertEqual(types, ['error'])


if __name__ == '__main__':
    unittest.main()
