"""
Tests for the Gamemaster changing a player's color (issue #50).
"""

from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.events import ColorEvent
from bingosync.models.enums import Role
from bingosync.models.game_type import GameType
from bingosync.models.colors import Color
import json

User = get_user_model()


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-test-cache-gm-color-change',
    }
})
@patch('bingosync.publish.requests.put')
class GamemasterColorChangeTestCase(TestCase):

    def setUp(self):
        self.room = Room.objects.create(
            name='Test Room', room_code='GMCOL1', passphrase='test123')
        Game.objects.create(
            room=self.room, seed=12345, size=5,
            game_type_value=GameType.hp_cos.value)

        self.gm = self._player('gm', Role.GAMEMASTER, Color.orange)
        self.player = self._player('player1', Role.PLAYER, Color.blue)
        self.other = self._player('player2', Role.PLAYER, Color.green)
        self.counter = self._player('counter', Role.COUNTER, Color.red)

        other_room = Room.objects.create(
            name='Other Room', room_code='GMCOL2', passphrase='x')
        self.outsider = Player.objects.create(
            room=other_room, name='outsider', role=Role.PLAYER,
            color_value=Color.pink.value)

        self.client = Client()

    def _player(self, name, role, color):
        user = User.objects.create_user(
            username=name, email=name + '@test.com', password='testpass123')
        player = Player.objects.create(
            room=self.room, user=user, name=name, role=role,
            color_value=color.value)
        player.test_user = user
        return player

    def _act_as(self, player):
        self.client.force_login(player.test_user)
        session = self.client.session
        session['authorized_rooms'] = {
            self.room.encoded_uuid: player.encoded_uuid}
        session.save()

    def _change_color(self, target, color):
        body = {'room': self.room.encoded_uuid, 'color': color}
        if target is not None:
            body['target_player_uuid'] = target.encoded_uuid
        return self.client.put(
            '/api/color', data=json.dumps(body),
            content_type='application/json')

    def test_gamemaster_can_change_players_color(self, mock_put):
        self._act_as(self.gm)
        response = self._change_color(self.player, 'purple')
        self.assertEqual(response.status_code, 200)

        self.player.refresh_from_db()
        self.gm.refresh_from_db()
        self.assertEqual(self.player.color, Color.purple)
        self.assertEqual(self.gm.color, Color.orange)

        event = ColorEvent.objects.get(player=self.player)
        self.assertEqual(event.changed_by, self.gm)
        self.assertEqual(event.player_color, Color.blue)
        self.assertEqual(event.color, Color.purple)

    def test_event_json_names_who_changed_it(self, mock_put):
        self._act_as(self.gm)
        self._change_color(self.player, 'purple')

        published = json.loads(mock_put.call_args.kwargs['data'])
        self.assertEqual(published['type'], 'color')
        self.assertEqual(published['player']['uuid'], self.player.encoded_uuid)
        self.assertEqual(published['player']['color'], 'purple')
        self.assertEqual(published['color'], 'purple')
        self.assertEqual(published['changed_by']['uuid'], self.gm.encoded_uuid)

    def test_own_color_change_has_no_changed_by(self, mock_put):
        self._act_as(self.player)
        response = self._change_color(None, 'yellow')
        self.assertEqual(response.status_code, 200)

        self.player.refresh_from_db()
        self.assertEqual(self.player.color, Color.yellow)
        event = ColorEvent.objects.get(player=self.player)
        self.assertIsNone(event.changed_by)
        self.assertIsNone(event.to_json()['changed_by'])

    def test_naming_yourself_is_an_own_color_change(self, mock_put):
        self._act_as(self.player)
        response = self._change_color(self.player, 'yellow')
        self.assertEqual(response.status_code, 200)
        self.player.refresh_from_db()
        self.assertEqual(self.player.color, Color.yellow)

    def test_player_cannot_change_another_players_color(self, mock_put):
        self._act_as(self.player)
        response = self._change_color(self.other, 'purple')
        self.assertEqual(response.status_code, 403)
        self.other.refresh_from_db()
        self.assertEqual(self.other.color, Color.green)
        self.assertFalse(ColorEvent.objects.exists())

    def test_counter_cannot_change_a_players_color(self, mock_put):
        self._act_as(self.counter)
        response = self._change_color(self.player, 'purple')
        self.assertEqual(response.status_code, 403)
        self.player.refresh_from_db()
        self.assertEqual(self.player.color, Color.blue)

    def test_only_players_colors_can_be_changed(self, mock_put):
        self._act_as(self.gm)
        response = self._change_color(self.counter, 'purple')
        self.assertEqual(response.status_code, 400)
        self.counter.refresh_from_db()
        self.assertEqual(self.counter.color, Color.red)

    def test_target_must_be_in_the_room(self, mock_put):
        self._act_as(self.gm)
        response = self._change_color(self.outsider, 'purple')
        self.assertEqual(response.status_code, 403)
        self.outsider.refresh_from_db()
        self.assertEqual(self.outsider.color, Color.pink)

    def test_unknown_target(self, mock_put):
        self._act_as(self.gm)
        response = self.client.put(
            '/api/color',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'target_player_uuid': 'nobody',
                'color': 'purple'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_invalid_color(self, mock_put):
        self._act_as(self.gm)
        for color in ('notacolor', 'blank'):
            response = self._change_color(self.player, color)
            self.assertEqual(response.status_code, 400)
        self.player.refresh_from_db()
        self.assertEqual(self.player.color, Color.blue)
