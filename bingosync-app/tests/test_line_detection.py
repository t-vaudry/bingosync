"""
Tests for server-side line/bingo detection: completing a row, column, or
diagonal in confirmed squares counts toward total_bingos_completed, exactly
once per line, in both lockout and non-lockout.
"""
from django.test import TestCase
from django.contrib.auth.hashers import make_password

from bingosync.models.user import User
from bingosync.models.rooms import Room, Game, Player, CompletedLine, LockoutMode
from bingosync.models.game_type import GameType
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.views import check_and_record_bingos


def _board():
    return [{"name": f"G{i}", "tier": 0} for i in range(1, 26)]


class LineDetectionTests(TestCase):

    def setUp(self):
        self.user_a = User.objects.create_user(
            username="alice", email="a@t.com", password="pw12345678")
        self.user_b = User.objects.create_user(
            username="bob", email="b@t.com", password="pw12345678")
        self.room = Room.objects.create(
            name="Lines", passphrase=make_password("pw"),
            hide_card=False, active=True)
        # non-lockout so both players can mark the same board freely
        self.game = Game.from_board(
            _board(), room=self.room, seed=1,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=LockoutMode.non_lockout.value, fog_of_war=False)
        self.player_a = Player.objects.create(
            room=self.room, user=self.user_a, name="alice",
            role=Role.PLAYER, color_value=Color.red.value)
        self.player_b = Player.objects.create(
            room=self.room, user=self.user_b, name="bob",
            role=Role.PLAYER, color_value=Color.blue.value)

    def _mark(self, player, slot, status='confirmed'):
        return self.game.update_goal(
            player, slot, player.color, False, claim_status=status)

    def test_completing_a_row_counts_one_bingo(self):
        for slot in range(1, 6):  # row-0
            self._mark(self.player_a, slot)
        self.assertEqual(check_and_record_bingos(self.game, self.player_a), 1)
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.total_bingos_completed, 1)
        self.assertTrue(CompletedLine.objects.filter(
            game=self.game, player=self.player_a, line="row-0").exists())

    def test_bingo_credited_only_once(self):
        for slot in range(1, 6):
            self._mark(self.player_a, slot)
        self.assertEqual(check_and_record_bingos(self.game, self.player_a), 1)
        # A second pass finds nothing new and does not re-increment.
        self.assertEqual(check_and_record_bingos(self.game, self.player_a), 0)
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.total_bingos_completed, 1)
        self.assertEqual(CompletedLine.objects.filter(
            game=self.game, player=self.player_a).count(), 1)

    def test_unconfirmed_square_does_not_complete_line(self):
        for slot in range(1, 5):  # 4 of row-0 confirmed
            self._mark(self.player_a, slot)
        self._mark(self.player_a, 5, status='under_review')  # 5th pending
        self.assertEqual(check_and_record_bingos(self.game, self.player_a), 0)
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.total_bingos_completed, 0)
        # Confirming the last square completes the line.
        self._mark(self.player_a, 5, status='confirmed')
        self.assertEqual(check_and_record_bingos(self.game, self.player_a), 1)

    def test_two_players_each_complete_a_line(self):
        for slot in range(1, 6):     # A completes row-0
            self._mark(self.player_a, slot)
        for slot in range(6, 11):    # B completes row-1
            self._mark(self.player_b, slot)
        self.assertEqual(check_and_record_bingos(self.game, self.player_a), 1)
        self.assertEqual(check_and_record_bingos(self.game, self.player_b), 1)
        self.user_a.refresh_from_db()
        self.user_b.refresh_from_db()
        self.assertEqual(self.user_a.total_bingos_completed, 1)
        self.assertEqual(self.user_b.total_bingos_completed, 1)

    def test_one_mark_completing_row_and_column_counts_two(self):
        # row-0 minus corner, col-0 minus corner...
        for slot in [2, 3, 4, 5, 6, 11, 16, 21]:
            self._mark(self.player_a, slot)
        self.assertEqual(check_and_record_bingos(self.game, self.player_a), 0)
        # ...then the shared corner (slot 1) completes both at once.
        self._mark(self.player_a, 1)
        self.assertEqual(check_and_record_bingos(self.game, self.player_a), 2)
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.total_bingos_completed, 2)
