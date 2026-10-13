"""
Tests for counter claim review.

Colors claim squares; players are associated with a color, and a counter
counts a color. Marks are approved by default and count immediately. A
counter can put a goal of their color in review (right-click on the board),
whoever marked it, take it back out (approve), or reject it, which removes
the color from the square and takes back what it counted for.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from bingosync.models.rooms import Room, Game, Player, CompletedLine
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.models.game_type import GameType
from bingosync.models.events import ClaimReviewEvent, ChatEvent
from bingosync.views import check_and_record_lockout_win
import json

User = get_user_model()

NON_LOCKOUT = 1
LOCKOUT = 2


class ClaimReviewTestBase(TestCase):

    lockout_mode = NON_LOCKOUT

    def setUp(self):
        self.gamemaster_user = User.objects.create_user(
            username='gamemaster', email='gm@test.com', password='testpass123')
        self.player_user = User.objects.create_user(
            username='player1', email='player1@test.com', password='testpass123')
        self.counter_user = User.objects.create_user(
            username='counter1', email='counter1@test.com', password='testpass123')

        self.room = Room.objects.create(
            name='Test Room', room_code='TEST01', passphrase='test123')
        board_json = [{"name": f"Goal {i}", "tier": i % 5} for i in range(1, 26)]
        self.game = Game.from_board(
            board_json,
            room=self.room,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=self.lockout_mode,
            seed=12345,
            fog_of_war=False
        )

        self.gamemaster = Player.objects.create(
            room=self.room, user=self.gamemaster_user, name='Gamemaster',
            role=Role.GAMEMASTER, color_value=Color.orange.value)
        self.player = Player.objects.create(
            room=self.room, user=self.player_user, name='Player1',
            role=Role.PLAYER, color_value=Color.red.value)
        self.counter = Player.objects.create(
            room=self.room, user=self.counter_user, name='Counter1',
            role=Role.COUNTER, color_value=Color.red.value,
            monitoring_color_value=Color.red.value)

        self.player_client = self._client_for(self.player)
        self.counter_client = self._client_for(self.counter)

    def _client_for(self, player):
        client = Client()
        client.force_login(player.user)
        session = client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: player.encoded_uuid}
        session.save()
        return client

    def _mark(self, slot, player=None):
        player = player or self.player
        client = (self.player_client if player == self.player
                  else self._client_for(player))
        response = client.put(
            '/api/select',
            data=json.dumps({'room': self.room.encoded_uuid, 'slot': slot,
                             'color': player.color.name, 'remove_color': False}),
            content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

    def _join(self, username, color, role=Role.PLAYER):
        user = User.objects.create_user(
            username=username, email=f'{username}@test.com', password='testpass123')
        return Player.objects.create(
            room=self.room, user=user, name=username, role=role,
            color_value=color.value)

    def _review(self, slot, action, client=None):
        return (client or self.counter_client).post(
            '/api/review-claim',
            data=json.dumps({'room': self.room.encoded_uuid, 'slot': slot,
                             'action': action}),
            content_type='application/json')

    def _square(self, slot):
        return self.game.squares[slot - 1]


class ClaimReviewEndpointTest(ClaimReviewTestBase):

    def test_mark_by_counted_player_is_approved_and_counts(self):
        self._mark(1)
        square = self._square(1)
        self.assertEqual(square.claim_status, 'confirmed')
        self.assertEqual(square.claimed_by, self.player)
        self.player_user.refresh_from_db()
        self.assertEqual(self.player_user.total_squares_marked, 1)

    def test_counter_can_put_goal_in_review(self):
        self._mark(1)
        response = self._review(1, 'under_review')
        self.assertEqual(response.status_code, 200)

        square = self._square(1)
        self.assertEqual(square.claim_status, 'under_review')
        self.assertEqual(square.reviewed_by, self.counter)
        self.assertIn(Color.red, square.color.colors)  # still marked
        self.assertTrue(ClaimReviewEvent.objects.filter(
            player=self.counter, square=square, action='under_review').exists())

    def test_counter_can_take_goal_out_of_review(self):
        self._mark(2)
        self._review(2, 'under_review')
        response = self._review(2, 'confirm')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._square(2).claim_status, 'confirmed')
        # Approving doesn't count the mark a second time
        self.player_user.refresh_from_db()
        self.assertEqual(self.player_user.total_squares_marked, 1)

    def test_approving_a_goal_not_in_review_is_refused(self):
        self._mark(3)
        self.assertEqual(self._review(3, 'confirm').status_code, 400)

    def test_putting_a_goal_already_in_review_in_review_is_refused(self):
        self._mark(3)
        self._review(3, 'under_review')
        self.assertEqual(self._review(3, 'under_review').status_code, 400)

    def test_unmarked_goal_cannot_be_reviewed(self):
        self.assertEqual(self._review(4, 'under_review').status_code, 400)

    def test_counter_can_reject_goal_in_review(self):
        self._mark(3)
        self._review(3, 'under_review')
        response = self._review(3, 'reject')
        self.assertEqual(response.status_code, 200)

        square = self._square(3)
        self.assertEqual(square.claim_status, 'rejected')
        self.assertEqual(square.reviewed_by, self.counter)
        self.assertIsNone(square.claimed_by)
        self.assertNotIn(self.player.color, square.color.colors)
        # The rejected mark no longer counts toward the player's total
        self.player_user.refresh_from_db()
        self.assertEqual(self.player_user.total_squares_marked, 0)

    def test_rejecting_a_goal_removes_its_bingo_line(self):
        for slot in range(1, 6):  # row 1
            self._mark(slot)
        self.player_user.refresh_from_db()
        self.assertEqual(self.player_user.total_bingos_completed, 1)

        self._review(3, 'under_review')
        self._review(3, 'reject')

        self.assertFalse(CompletedLine.objects.filter(
            game=self.game, player=self.player).exists())
        self.player_user.refresh_from_db()
        self.assertEqual(self.player_user.total_bingos_completed, 0)

    def test_goal_in_review_still_completes_a_line(self):
        for slot in range(1, 5):
            self._mark(slot)
        self._mark(5)  # completes row 1
        self._review(5, 'under_review')
        self.assertTrue(CompletedLine.objects.filter(
            game=self.game, player=self.player, line='row-0').exists())

    def test_non_counter_cannot_review_claim(self):
        self._mark(4)
        response = self._review(4, 'under_review', client=self.player_client)
        self.assertEqual(response.status_code, 403)

    def test_counter_cannot_review_another_colors_goal(self):
        green = self._join('player2', Color.green)
        self._mark(5, player=green)
        self.assertEqual(self._review(5, 'under_review').status_code, 403)

    def test_counter_reviews_their_color_whoever_marked_it(self):
        # Colors claim squares: a second red player (or the same person
        # rejoining as a new player) marks a red goal; the red counter
        # reviews it like any other red goal.
        teammate = self._join('player2', Color.red)
        self._mark(8, player=teammate)
        self.assertEqual(self._review(8, 'under_review').status_code, 200)
        self.assertEqual(self._review(8, 'reject').status_code, 200)
        self.assertNotIn(Color.red, self._square(8).color.colors)

    def test_rejecting_leaves_other_colors_on_the_square(self):
        green = self._join('player2', Color.green)
        self._mark(9)                 # red
        self._mark(9, player=green)   # and green (non-lockout)
        self._review(9, 'under_review')
        self._review(9, 'reject')
        square = self._square(9)
        self.assertEqual(square.color.colors, [Color.green])
        self.assertEqual(square.claim_status, 'confirmed')  # green still counts

    def test_invalid_action_rejected(self):
        self._mark(6)
        self.assertEqual(self._review(6, 'invalid_action').status_code, 400)

    def test_old_flow_pending_claim_can_still_be_approved(self):
        # Squares left waiting under the previous review flow
        square = self._square(7)
        square.claimed_by = self.player
        square.claim_status = 'pending_decision'
        square_color = square.color
        square_color.add(self.player.color)
        square.color = square_color
        square.save()

        self.assertEqual(self._review(7, 'confirm').status_code, 200)
        self.assertEqual(self._square(7).claim_status, 'confirmed')
        self.player_user.refresh_from_db()
        self.assertEqual(self.player_user.total_squares_marked, 1)


class LockoutReviewTest(ClaimReviewTestBase):

    lockout_mode = LOCKOUT

    def test_goal_in_review_still_counts_toward_the_win(self):
        for slot in range(1, 13):
            self._mark(slot)
        self._mark(13)  # 13th goal wins
        self.game.refresh_from_db()
        self.assertEqual(self.game.winner, self.player)
        # Putting a winning goal in review doesn't undo the win
        self._review(13, 'under_review')
        self.game.refresh_from_db()
        self.assertEqual(self.game.winner, self.player)

    def test_rejecting_a_goal_withdraws_a_win_that_no_longer_holds(self):
        for slot in range(1, 14):
            self._mark(slot)
        self.game.refresh_from_db()
        self.assertEqual(self.game.winner, self.player)
        self.player_user.refresh_from_db()
        self.assertEqual(self.player_user.wins, 1)

        self._review(13, 'under_review')
        self._review(13, 'reject')

        self.game.refresh_from_db()
        self.assertIsNone(self.game.winner)
        self.player_user.refresh_from_db()
        self.assertEqual(self.player_user.wins, 0)
        self.assertTrue(ChatEvent.objects.filter(
            body__contains="win was withdrawn").exists())

    def test_rejecting_a_goal_keeps_a_win_that_still_holds(self):
        for slot in range(1, 15):  # 14 goals, one more than needed
            self._mark(slot)
        self._review(14, 'under_review')
        self._review(14, 'reject')
        self.game.refresh_from_db()
        self.assertEqual(self.game.winner, self.player)

    def test_win_detection_counts_goals_in_review(self):
        for slot in range(1, 14):
            self.game.update_goal(
                self.player, slot, self.player.color, False,
                claim_status='under_review' if slot == 13 else 'confirmed')
        self.assertEqual(
            check_and_record_lockout_win(self.game, self.player), self.player)

    def test_players_sharing_a_color_win_together(self):
        # Colors claim squares: two red players reach 13 between them
        teammate = self._join('player2', Color.red)
        other = self._join('player3', Color.green)
        for slot in range(1, 8):
            self._mark(slot)
        for slot in range(8, 14):
            self._mark(slot, player=teammate)

        self.game.refresh_from_db()
        self.assertIsNotNone(self.game.winner)
        for player, field, expected in ((self.player, 'wins', 1),
                                        (teammate, 'wins', 1),
                                        (other, 'losses', 1)):
            player.user.refresh_from_db()
            self.assertEqual(getattr(player.user, field), expected, player.name)
        # Named by color: two players share it
        self.assertTrue(ChatEvent.objects.filter(
            body__contains="red reached 13 goals").exists())


class CountingAColorTest(ClaimReviewTestBase):

    def _assign(self, color, client=None):
        return (client or self.counter_client).post(
            '/api/assign-counter',
            data=json.dumps({'room': self.room.encoded_uuid,
                             'counter_player_uuid': self.counter.encoded_uuid,
                             'monitored_color': color}),
            content_type='application/json')

    def test_counter_takes_on_the_color_they_count(self):
        green = self._join('player2', Color.green)
        self.assertEqual(self._assign('green').status_code, 200)
        self.counter.refresh_from_db()
        self.assertEqual(self.counter.monitoring_color, Color.green)
        self.assertEqual(self.counter.color, Color.green)
        # Named after the color's only player
        self.assertTrue(ChatEvent.objects.filter(
            body__contains=f"is now counting {green.name}").exists())

    def test_color_shared_by_players_is_named_by_color(self):
        self._join('player2', Color.red)
        self._assign('red')
        self.assertTrue(ChatEvent.objects.filter(
            body__contains="is now counting red").exists())

    def test_blank_and_unknown_colors_are_refused(self):
        self.assertEqual(self._assign('blank').status_code, 400)
        self.assertEqual(self._assign('chartreuse').status_code, 400)

    def test_line_is_credited_once_per_color(self):
        teammate = self._join('player2', Color.red)
        for slot in range(1, 5):
            self._mark(slot)
        self._mark(5, player=teammate)  # completes row 1 for red
        self._mark(6, player=teammate)  # a later red mark finds it done
        self.assertEqual(CompletedLine.objects.filter(
            game=self.game, line='row-0').count(), 1)
