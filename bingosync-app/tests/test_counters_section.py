"""
Counters are listed in their own "Counters" section of the players panel, not
among the players, and the [C] / [S] role markers are gone.
"""
import re

from django.test import TestCase, Client
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.models.game_type import GameType


class CountersSectionTest(TestCase):

    def setUp(self):
        self.room = Room.objects.create(
            name='Test Room', room_code='TEST02', passphrase='', active=True)
        Game.from_board(
            [{"name": f"Goal {i}", "tier": 1} for i in range(25)],
            room=self.room, game_type_value=GameType.hp_cos.value,
            lockout_mode_value=1, seed=1, fog_of_war=False)
        self.players = {}
        for name, role in [('gmname', Role.GAMEMASTER), ('plname', Role.PLAYER),
                           ('ctname', Role.COUNTER), ('spname', Role.SPECTATOR)]:
            self.players[name] = Player.objects.create(
                room=self.room, name=name, role=role, color_value=Color.red.value)

    def _html(self):
        viewer = self.players['gmname']
        client = Client()
        session = client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: viewer.encoded_uuid}
        session.save()
        response = client.get(f'/room/{self.room.encoded_uuid}')
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_counter_listed_under_counters_section_not_players(self):
        html = self._html()
        panel = html[html.index('id="players-panel"'):]
        self.assertIn('class="counters-header">Counters<', panel)
        counters = panel.index('counters-section')
        spectators = panel.index('spectators-section')
        self.assertLess(counters, panel.index('ctname'))
        self.assertLess(panel.index('ctname'), spectators)
        # Player and GM entries come before the Counters section
        self.assertLess(panel.index('plname'), counters)
        self.assertLess(panel.index('gmname'), counters)

    def test_no_c_or_s_markers(self):
        html = self._html()
        self.assertNotIn('[C]', html)
        self.assertNotIn('[S]', html)
        self.assertIn('[GM]', html)

    def test_no_counters_section_without_counters(self):
        self.players['ctname'].delete()
        self.assertNotIn('counters-section', self._html())
