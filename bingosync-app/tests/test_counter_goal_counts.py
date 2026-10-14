"""
Tests for a counter's goal counts ("3/6 Gnomes").

The card generator says how many each goal takes (`amount`), which goals
counting it also advances (`triggers`, by goal id) and how far those linked
counts may go (`uniqueAmount`). A counter counts the goals of the color
they're counting; the counts are private to that counter (two counters on one
color count independently), kept per game and color, and never broadcast.
"""
from unittest import mock

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from bingosync.generators.bingo_generator import (
    goal_counting_fields, process_card)
from bingosync.models.rooms import Room, Game, Player, CounterTally
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.models.game_type import GameType
import json

User = get_user_model()

NON_LOCKOUT = 1

# Slots 1-3 are counted goals; 3's triggers advance 1 and 2. Slot 4 is a
# one-step goal whose only job is to advance 1. Every other slot is a plain
# one-step goal.
STARS = {"name": "Collect 5 stars", "tier": 1, "goal_key": "stars",
         "amount": 5, "unique_amount": 5, "triggers": []}
CARDS = {"name": "Collect 2x3 cards", "tier": 1, "goal_key": "cards",
         "amount": 6, "unique_amount": 3, "triggers": []}
GNOMES = {"name": "Throw 3 gnomes", "tier": 1, "goal_key": "gnomes",
          "amount": 3, "unique_amount": 3, "triggers": ["stars", "cards"]}
GNOME_STAR = {"name": "Spell challenge with a gnome", "tier": 1,
              "goal_key": "gnome-star", "amount": 1, "unique_amount": 1,
              "triggers": ["stars"]}


def board_json():
    plain = [{"name": f"Goal {i}", "tier": 1} for i in range(5, 26)]
    return [STARS, CARDS, GNOMES, GNOME_STAR] + plain


class GoalCountingFieldsTest(TestCase):

    def test_keeps_the_generators_counting_fields(self):
        fields = goal_counting_fields({
            "id": "cards-23", "name": "Collect 23 cards", "amount": 46,
            "uniqueAmount": 23, "triggers": ["cards-37"]})
        self.assertEqual(fields, {"goal_key": "cards-23", "amount": 46,
                                  "unique_amount": 23,
                                  "triggers": ["cards-37"]})

    def test_unique_amount_defaults_to_the_amount(self):
        fields = goal_counting_fields({"id": "matches-6", "amount": 6,
                                       "triggers": None})
        self.assertEqual(fields["unique_amount"], 6)
        self.assertEqual(fields["triggers"], [])

    def test_a_goal_without_counting_fields_is_one_step(self):
        self.assertEqual(goal_counting_fields({"name": "Custom goal"}), {
            "goal_key": "", "amount": 1, "unique_amount": 1, "triggers": []})

    def test_nonsense_values_fall_back(self):
        fields = goal_counting_fields({"id": 7, "amount": "lots",
                                       "uniqueAmount": 99,
                                       "triggers": ["ok", 3]})
        self.assertEqual(fields, {"goal_key": "", "amount": 1,
                                  "unique_amount": 1, "triggers": ["ok"]})

    def test_process_card_passes_them_through(self):
        card = {"seed": "1", "objectives": [None] + [
            {"name": f"Goal {i}", "difficulty": 1, "id": f"g{i}",
             "amount": 2, "triggers": None} for i in range(25)]}
        _, board = process_card(card, "1", 5)
        self.assertEqual(board[0]["goal_key"], "g0")
        self.assertEqual(board[0]["amount"], 2)

    def test_hp_cos_cards_carry_counting_fields(self):
        _, board = GameType.hp_cos.generator_instance().get_card("424242", [], 5)
        self.assertTrue(all(goal["goal_key"] for goal in board))
        self.assertTrue(any(goal["amount"] > 1 for goal in board))


class CounterGoalCountsTestBase(TestCase):

    def setUp(self):
        self.room = Room.objects.create(
            name='Test Room', room_code='TEST01', passphrase='test123')
        self.game = Game.from_board(
            board_json(), room=self.room,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=NON_LOCKOUT, seed=12345, fog_of_war=False)
        self.player = self._join('player1', Role.PLAYER, Color.red)
        self.counter = self._join('counter1', Role.COUNTER, Color.red,
                                  monitoring=Color.red)
        self.player_client = self._client_for(self.player)
        self.counter_client = self._client_for(self.counter)

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

    def _get(self, client=None):
        return (client or self.counter_client).get(
            '/api/counter-counts', {'room': self.room.encoded_uuid})

    def _post(self, action, client=None, **body):
        body.update(room=self.room.encoded_uuid, action=action)
        return (client or self.counter_client).post(
            '/api/counter-counts', data=json.dumps(body),
            content_type='application/json')

    def _ok(self, action, client=None, **body):
        response = self._post(action, client, **body)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def _count(self, slot, delta=1, times=1, client=None):
        for _ in range(times):
            tally = self._ok('change', client, slot=slot, delta=delta)
        return tally

    def _mark(self, slot, remove=False):
        response = self.player_client.put(
            '/api/select',
            data=json.dumps({'room': self.room.encoded_uuid, 'slot': slot,
                             'color': 'red', 'remove_color': remove}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

    def _review(self, slot, action):
        response = self.counter_client.post(
            '/api/review-claim',
            data=json.dumps({'room': self.room.encoded_uuid, 'slot': slot,
                             'action': action}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)


class CountingTest(CounterGoalCountsTestBase):

    def test_squares_keep_their_counting_fields(self):
        gnomes = self.game.squares[2]
        self.assertEqual((gnomes.goal_key, gnomes.amount, gnomes.unique_amount,
                          gnomes.triggers), ("gnomes", 3, 3, ["stars", "cards"]))
        self.assertTrue(gnomes.is_counted)
        self.assertTrue(self.game.squares[3].is_counted)  # one step, triggers
        self.assertFalse(self.game.squares[4].is_counted)

    def test_the_board_json_leaves_counting_fields_out(self):
        board = self.client.get(f'/room/{self.room.encoded_uuid}/board').json()
        self.assertNotIn('amount', board[0])
        self.assertNotIn('triggers', board[0])

    def test_counter_sees_only_counted_goals_starting_at_zero(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        tally = response.json()
        self.assertEqual(tally['color'], 'red')
        self.assertEqual(sorted(tally['goals'], key=int), ['1', '2', '3', '4'])
        self.assertEqual(tally['goals']['2'],
                         {'amount': 6, 'unique_amount': 3})
        self.assertEqual(tally['counts'], {})
        self.assertIsNone(tally['saved_at'])
        self.assertEqual(tally['dismissed'], [])

    def test_count_up_and_down(self):
        self._count(1, times=2)
        tally = self._count(1, delta=-1)
        self.assertEqual(tally['counts'], {'1': 1})
        self.assertEqual(self._get().json()['counts'], {'1': 1})

    def test_counts_stay_between_zero_and_the_amount(self):
        self.assertEqual(self._post('change', slot=1, delta=-1).status_code, 400)
        self._count(1, times=5)
        self.assertEqual(self._post('change', slot=1, delta=1).status_code, 400)
        self.assertEqual(self._get().json()['counts'], {'1': 5})

    def test_only_counted_goals_and_single_steps(self):
        self.assertEqual(self._post('change', slot=5, delta=1).status_code, 400)
        self.assertEqual(self._post('change', slot=30, delta=1).status_code, 400)
        self.assertEqual(self._post('change', slot=1, delta=2).status_code, 400)
        self.assertEqual(self._post('change', slot=1).status_code, 400)
        self.assertEqual(self._post('explode', slot=1).status_code, 400)

    def test_counting_a_goal_counts_the_goals_it_triggers(self):
        tally = self._count(3)
        self.assertEqual(tally['counts'], {'3': 1, '1': 1, '2': 1})
        tally = self._count(4)  # one step, triggers stars
        self.assertEqual(tally['counts'], {'3': 1, '1': 2, '2': 1, '4': 1})
        tally = self._count(3, delta=-1)
        self.assertEqual(tally['counts'], {'3': 0, '1': 1, '2': 0, '4': 1})

    def test_linked_counts_stop_at_their_unique_amount(self):
        # Cards takes 6 but only 3 can come from linked goals
        self._count(2, times=3)
        tally = self._count(3)
        self.assertEqual(tally['counts']['3'], 1)
        self.assertEqual(tally['counts']['2'], 3)
        self.assertEqual(tally['counts']['1'], 1)

    def test_linked_counts_dont_go_below_zero(self):
        self._count(3)
        self._count(1, delta=-1)
        tally = self._count(3, delta=-1)
        self.assertEqual(tally['counts'], {'3': 0, '1': 0, '2': 0})

    def test_counting_isnt_broadcast_or_announced(self):
        with mock.patch('bingosync.publish._publish_json') as publish:
            self._count(1)
            self._ok('save')
        publish.assert_not_called()


class WhoCountsTest(CounterGoalCountsTestBase):

    def test_only_counters_count(self):
        spectator = self._join('watcher', Role.SPECTATOR, Color.blank)
        for client in (self.player_client, self._client_for(spectator)):
            self.assertEqual(self._get(client).status_code, 403)
            self.assertEqual(
                self._post('change', client, slot=1, delta=1).status_code, 403)

    def test_counter_must_choose_a_color_first(self):
        counter = self._join('counter2', Role.COUNTER, Color.blue)
        client = self._client_for(counter)
        self.assertEqual(self._get(client).status_code, 400)
        self.assertEqual(
            self._post('change', client, slot=1, delta=1).status_code, 400)

    def test_counters_on_one_color_count_separately(self):
        other = self._join('counter2', Role.COUNTER, Color.red,
                           monitoring=Color.red)
        other_client = self._client_for(other)
        self._count(1, times=2)
        self._count(1, client=other_client)
        self.assertEqual(self._get().json()['counts'], {'1': 2})
        self.assertEqual(self._get(other_client).json()['counts'], {'1': 1})

    def test_each_color_keeps_its_own_counts(self):
        self._count(1, times=2)
        self.counter.monitoring_color_value = Color.blue.value
        self.counter.save()
        tally = self._get().json()
        self.assertEqual((tally['color'], tally['counts']), ('blue', {}))
        self._count(1)
        self.counter.monitoring_color_value = Color.red.value
        self.counter.save()
        self.assertEqual(self._get().json()['counts'], {'1': 2})

    def test_a_new_card_starts_from_zero(self):
        self._count(1, times=2)
        Game.from_board(
            board_json(), room=self.room,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=NON_LOCKOUT, seed=999, fog_of_war=False)
        self.assertEqual(self._get().json()['counts'], {})


class SavedStateTest(CounterGoalCountsTestBase):

    def test_load_goes_back_to_the_saved_counts(self):
        self._count(1, times=2)
        tally = self._ok('save')
        self.assertIsNotNone(tally['saved_at'])
        self._count(1, times=2)
        self._count(2)
        tally = self._ok('load')
        self.assertEqual(tally['counts'], {'1': 2})
        # The saved state stays for the next time
        self._count(1)
        self.assertEqual(self._ok('load')['counts'], {'1': 2})

    def test_nothing_to_load_until_saved(self):
        self.assertEqual(self._post('load').status_code, 400)
        self._ok('save')
        tally = self._ok('clear')
        self.assertIsNone(tally['saved_at'])
        self.assertEqual(self._post('load').status_code, 400)

    def test_reset_clears_counts_saved_state_and_dismissals(self):
        self._count(1)
        self._ok('save')
        self._mark(2)
        self._ok('dismiss', slot=2)
        tally = self._ok('reset')
        self.assertEqual((tally['counts'], tally['saved_at'], tally['dismissed']),
                         ({}, None, []))


class MarkedBeforeCountedTest(CounterGoalCountsTestBase):

    def test_dismiss_a_counted_goal(self):
        self._mark(1)
        self.assertEqual(self._ok('dismiss', slot=1)['dismissed'], [1])
        self.assertEqual(self._ok('dismiss', slot=1)['dismissed'], [1])
        self.assertEqual(self._post('dismiss', slot=5).status_code, 400)

    def test_load_brings_dismissed_alerts_back(self):
        self._ok('save')
        self._mark(1)
        self._ok('dismiss', slot=1)
        self.assertEqual(self._ok('load')['dismissed'], [])

    def test_unmarking_brings_the_alert_back_for_the_next_mark(self):
        self._mark(1)
        self._ok('dismiss', slot=1)
        self._mark(1, remove=True)
        self.assertEqual(self._get().json()['dismissed'], [])

    def test_counter_unmarking_brings_the_alert_back_for_the_next_mark(self):
        self._mark(1)
        self._ok('dismiss', slot=1)
        response = self.counter_client.put(
            '/api/select',
            data=json.dumps({'room': self.room.encoded_uuid, 'slot': 1,
                             'color': 'red', 'remove_color': True}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(self._get().json()['dismissed'], [])

    def test_approving_from_review_dismisses_it_for_that_counter(self):
        other = self._join('counter2', Role.COUNTER, Color.red,
                           monitoring=Color.red)
        self._mark(1)
        self._review(1, 'under_review')
        self._review(1, 'confirm')
        self.assertEqual(self._get().json()['dismissed'], [1])
        self.assertEqual(
            self._get(self._client_for(other)).json()['dismissed'], [])

    def test_approving_a_one_step_goal_records_nothing(self):
        self._mark(5)
        self._review(5, 'under_review')
        self._review(5, 'confirm')
        self.assertFalse(CounterTally.objects.exists())
