"""
Tests for the Commentator role: sees the whole board and every counter's goal
counts (per player), but can't mark, count or review.
"""
import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from bingosync.forms import JoinRoomForm
from bingosync.models.colors import Color
from bingosync.models.enums import Role
from bingosync.models.game_type import GameType
from bingosync.models.rooms import CounterTally, Game, Player, Room
from bingosync.permissions import check_permission
from tests.test_counter_goal_counts import NON_LOCKOUT, board_json

User = get_user_model()


class CommentatorRoleTest(TestCase):

    def setUp(self):
        self.room = Room.objects.create(
            name='Test Room', room_code='TEST01', passphrase='', active=True)
        self.game = Game.from_board(
            board_json(), room=self.room,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=NON_LOCKOUT, seed=12345, fog_of_war=False)
        self.player = self._join('ann', Role.PLAYER, Color.red)
        self.counter = self._join('counter1', Role.COUNTER, Color.red,
                                  monitoring=Color.red)
        self.commentator = self._join('cass', Role.COMMENTATOR, Color.blank)

    def _join(self, username, role, color, monitoring=None):
        user = User.objects.create_user(
            username=username, email=f'{username}@test.com',
            password='testpass123')
        return Player.objects.create(
            room=self.room, user=user, name=username, role=role,
            color_value=color.value,
            monitoring_color_value=monitoring.value if monitoring else None)

    def _client_for(self, player):
        client = Client()
        client.force_login(player.user)
        session = client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: player.encoded_uuid}
        session.save()
        return client

    def _counts(self, player):
        return self._client_for(player).get(
            '/api/commentator-counts', {'room': self.room.encoded_uuid})

    def test_permissions(self):
        self.assertTrue(check_permission(self.commentator, 'view_board'))
        self.assertTrue(check_permission(self.commentator, 'view_counts'))
        self.assertTrue(check_permission(self.commentator, 'chat'))
        self.assertFalse(check_permission(self.commentator, 'mark_square'))
        self.assertFalse(check_permission(self.player, 'view_counts'))

    def test_has_no_color_and_is_an_observer(self):
        self.assertEqual(self.commentator.color, Color.blank)
        self.assertTrue(self.commentator.is_observer)
        self.assertFalse(self.commentator.is_spectator)
        self.assertTrue(self.commentator.to_json()['is_commentator'])

    def test_cannot_mark_goals(self):
        response = self._client_for(self.commentator).put(
            '/api/select',
            data=json.dumps({'room': self.room.encoded_uuid, 'slot': 1,
                             'color': 'red', 'remove_color': False}),
            content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_cannot_count_or_review(self):
        client = self._client_for(self.commentator)
        self.assertEqual(client.get(
            '/api/counter-counts', {'room': self.room.encoded_uuid}).status_code, 403)
        response = client.post(
            '/api/review-claim',
            data=json.dumps({'room': self.room.encoded_uuid, 'slot': 1,
                             'action': 'under_review'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_sees_every_counters_counts_per_player(self):
        other = self._join('counter2', Role.COUNTER, Color.blue,
                           monitoring=Color.blue)
        tally = CounterTally.for_update(self.game, self.counter, Color.red)
        tally.change(list(self.game.squares), 3, 1)
        tally.save()
        CounterTally.for_update(self.game, other, Color.blue)

        response = self._counts(self.commentator)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(sorted(data['goals']), ['1', '2', '3', '4'])
        by_color = {t['color']: t for t in data['tallies']}
        # The color is labelled with its player; a color nobody plays by name
        self.assertEqual(by_color['red']['label'], 'ann')
        self.assertEqual(by_color['red']['counter'], 'counter1')
        self.assertEqual(by_color['red']['counts'], {'3': 1, '1': 1, '2': 1})
        self.assertEqual(by_color['blue']['label'], 'blue')

    def test_leaves_out_private_tally_details(self):
        tally = CounterTally.for_update(self.game, self.counter, Color.red)
        tally.save_state()
        tally.dismissed = [1]
        tally.save()
        tally_json = self._counts(self.commentator).json()['tallies'][0]
        self.assertEqual(set(tally_json),
                         {'color', 'label', 'counter', 'counts', 'completed'})

    def test_skips_empty_tallies_of_counters_who_moved_on(self):
        CounterTally.for_update(self.game, self.counter, Color.blue)
        self.assertEqual(self._counts(self.commentator).json()['tallies'], [])

    def test_only_commentators_see_the_counts(self):
        for who in (self.player, self.counter):
            self.assertEqual(self._counts(who).status_code, 403)

    def test_a_commentator_alone_does_not_keep_a_room_active(self):
        self.player.delete()
        self.counter.delete()
        self.room.update_active()
        self.assertFalse(Room.objects.get(pk=self.room.pk).active)

    def test_can_join_as_commentator(self):
        form = JoinRoomForm(data={
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'newcomer', 'passphrase': '',
            'role': Role.COMMENTATOR}, room=self.room)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.create_player().role, Role.COMMENTATOR)

    def test_cannot_join_an_inactive_room_as_commentator(self):
        self.room.active = False
        self.room.save()
        form = JoinRoomForm(data={
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'newcomer', 'passphrase': '',
            'role': Role.COMMENTATOR}, room=self.room)
        self.assertFalse(form.is_valid())

    def test_room_page_shows_the_counts_panel(self):
        page = self._client_for(self.commentator).get(
            f'/room/{self.room.encoded_uuid}')
        self.assertContains(page, 'Commentating as')
        self.assertContains(page, 'id="commentator-counts"')
        self.assertNotContains(page, 'id="color-chooser"')
        other = self._client_for(self.player).get(
            f'/room/{self.room.encoded_uuid}')
        self.assertNotContains(other, 'id="commentator-counts"')
