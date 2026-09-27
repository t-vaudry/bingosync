"""
Tests for lazy achievement evaluation and its display on the profile page.
"""
from django.test import TestCase, Client

from bingosync.models.user import User
from bingosync.models.rooms import Room, Game, Player, CompletedLine, LockoutMode
from bingosync.models.game_type import GameType
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.achievements import evaluate_achievements


def _earned(user):
    return {a["code"] for a in evaluate_achievements(user) if a["earned"]}


class AchievementTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="a@t.com", password="pw12345678")
        self.room = Room.objects.create(
            name="R", room_code=Room.generate_room_code(),
            passphrase="", hide_card=False, active=True)
        self.game = Game.from_board(
            [{"name": f"G{i}", "tier": 0} for i in range(1, 26)],
            room=self.room, seed=1, game_type_value=GameType.hp_cos.value,
            lockout_mode_value=LockoutMode.lockout.value)
        self.player = Player.objects.create(
            room=self.room, user=self.user, name="alice",
            role=Role.PLAYER, color_value=Color.red.value)
        self.client = Client()

    def _line(self, key):
        CompletedLine.objects.create(game=self.game, player=self.player, line=key)

    def test_new_user_earns_nothing(self):
        self.assertEqual(_earned(self.user), set())

    def test_stat_milestones(self):
        self.user.total_squares_marked = 100
        self.user.wins = 1
        self.user.total_bingos_completed = 1
        self.user.save()
        codes = _earned(self.user)
        self.assertIn("first_square", codes)
        self.assertIn("hundred_squares", codes)
        self.assertIn("first_win", codes)
        self.assertIn("first_bingo", codes)
        self.assertNotIn("many_squares", codes)   # 500 not reached
        self.assertNotIn("ten_wins", codes)

    def test_pattern_achievements(self):
        self._line("row-0")
        self._line("col-2")
        self._line("diag-main")
        codes = _earned(self.user)
        self.assertIn("row", codes)
        self.assertIn("column", codes)
        self.assertIn("diagonal", codes)
        self.assertNotIn("blackout", codes)   # not a full board

    def test_blackout_requires_all_five_rows(self):
        for r in range(4):
            self._line(f"row-{r}")
        self.assertNotIn("blackout", _earned(self.user))
        self._line("row-4")
        self.assertIn("blackout", _earned(self.user))

    def test_profile_shows_achievements(self):
        self.user.total_squares_marked = 1
        self.user.save()
        resp = self.client.get(f"/users/{self.user.username}")
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertIn("Achievements", body)
        self.assertIn("First Steps", body)
