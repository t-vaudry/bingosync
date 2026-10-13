"""
Tests for the room's Counter Settings panel: a counter picks their review
style in the room (the same preference as on their profile), and it's saved
to their account.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.models.game_type import GameType
from bingosync.models.user import ReviewStyle
import json

User = get_user_model()


class CounterSettingsTest(TestCase):

    def setUp(self):
        self.room = Room.objects.create(
            name='Test Room', room_code='TEST01', passphrase='test123')
        Game.from_board(
            [{"name": f"Goal {i}", "tier": 1} for i in range(25)],
            room=self.room, game_type_value=GameType.hp_cos.value,
            lockout_mode_value=1, seed=1, fog_of_war=False)
        self.counter = self._join('counter1', Role.COUNTER)
        self.player = self._join('player1', Role.PLAYER)

    def _join(self, username, role):
        user = User.objects.create_user(
            username=username, email=f'{username}@test.com',
            password='testpass123')
        return Player.objects.create(
            room=self.room, user=user, name=username, role=role,
            color_value=Color.red.value)

    def _client_for(self, player):
        client = Client()
        client.force_login(player.user)
        session = client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: player.encoded_uuid}
        session.save()
        return client

    def _set(self, client, style):
        return client.post('/api/review-style',
                           data=json.dumps({'review_style': style}),
                           content_type='application/json')

    def test_counter_sees_the_panel_with_their_style_chosen(self):
        self.counter.user.review_style = ReviewStyle.HOVER
        self.counter.user.save()
        response = self._client_for(self.counter).get(
            f'/room/{self.room.encoded_uuid}')
        self.assertContains(response, 'Counter Settings')
        self.assertContains(
            response, 'name="review_style" value="hover" checked')
        for value in ReviewStyle.values:
            self.assertContains(response, f'value="{value}"')

    def test_players_dont_see_the_panel(self):
        response = self._client_for(self.player).get(
            f'/room/{self.room.encoded_uuid}')
        self.assertNotContains(response, 'Counter Settings')

    def test_saves_the_style_to_the_account(self):
        response = self._set(self._client_for(self.counter), ReviewStyle.BUTTONS)
        self.assertEqual(response.status_code, 200, response.content)
        self.counter.user.refresh_from_db()
        self.assertEqual(self.counter.user.review_style, ReviewStyle.BUTTONS)

    def test_rejects_an_unknown_style(self):
        response = self._set(self._client_for(self.counter), 'telepathy')
        self.assertEqual(response.status_code, 400)
        self.counter.user.refresh_from_db()
        self.assertEqual(self.counter.user.review_style, ReviewStyle.LIST)

    def test_needs_a_login_and_a_post(self):
        self.assertEqual(self._set(Client(), ReviewStyle.CLICK).status_code, 403)
        self.assertEqual(
            self._client_for(self.counter).get('/api/review-style').status_code, 405)
