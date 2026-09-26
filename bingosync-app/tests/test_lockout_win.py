"""
Tests for lockout win detection: first player to a majority of *confirmed*
squares (13 on a 5x5) wins, exactly once, with correct win/loss stats.
"""
import json

from django.test import TestCase, Client
from django.contrib.auth.hashers import make_password

from bingosync.models.user import User
from bingosync.models.rooms import Room, Game, Player, LockoutMode
from bingosync.models.game_type import GameType
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.models.events import ChatEvent
from bingosync.views import check_and_record_lockout_win


def _board():
    return [{"name": f"Goal {i}", "tier": 0} for i in range(1, 26)]


class LockoutWinTests(TestCase):

    def setUp(self):
        self.user_a = User.objects.create_user(
            username="alice", email="alice@test.com", password="testpass123")
        self.user_b = User.objects.create_user(
            username="bob", email="bob@test.com", password="testpass123")
        self.room = Room.objects.create(
            name="Lockout Room", passphrase=make_password("pw"),
            hide_card=False, active=True)
        self.game = Game.from_board(
            _board(), room=self.room, seed=1,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=LockoutMode.lockout.value, fog_of_war=False)
        self.player_a = Player.objects.create(
            room=self.room, user=self.user_a, name="alice",
            role=Role.PLAYER, color_value=Color.red.value)
        self.player_b = Player.objects.create(
            room=self.room, user=self.user_b, name="bob",
            role=Role.PLAYER, color_value=Color.blue.value)

    def _mark(self, game, player, slot):
        return game.update_goal(
            player, slot, player.color, False, claim_status='confirmed')

    def test_first_to_thirteen_wins(self):
        # 12 confirmed squares: not a win yet.
        for slot in range(1, 13):
            self._mark(self.game, self.player_a, slot)
            self.assertIsNone(
                check_and_record_lockout_win(self.game, self.player_a),
                f"win fired early at {slot} squares")

        # The 13th confirmed square wins.
        self._mark(self.game, self.player_a, 13)
        self.assertEqual(
            check_and_record_lockout_win(self.game, self.player_a),
            self.player_a)

        self.game.refresh_from_db()
        self.assertEqual(self.game.winner_id, self.player_a.id)

        self.user_a.refresh_from_db()
        self.user_b.refresh_from_db()
        self.assertEqual(self.user_a.wins, 1)
        self.assertEqual(self.user_a.losses, 0)
        self.assertEqual(self.user_b.wins, 0)
        self.assertEqual(self.user_b.losses, 1)

        win_msgs = ChatEvent.objects.filter(
            player__room=self.room, is_system_message=True,
            body__contains="won the game")
        self.assertEqual(win_msgs.count(), 1)

    def test_win_is_recorded_only_once(self):
        for slot in range(1, 14):
            self._mark(self.game, self.player_a, slot)
        self.assertEqual(
            check_and_record_lockout_win(self.game, self.player_a),
            self.player_a)

        # A further confirmed square must not re-award the win.
        self._mark(self.game, self.player_a, 14)
        self.assertIsNone(
            check_and_record_lockout_win(self.game, self.player_a))

        self.user_a.refresh_from_db()
        self.user_b.refresh_from_db()
        self.assertEqual(self.user_a.wins, 1)
        self.assertEqual(self.user_b.losses, 1)

    def test_non_lockout_never_wins(self):
        non_lockout = Game.from_board(
            _board(), room=self.room, seed=2,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=LockoutMode.non_lockout.value, fog_of_war=False)
        for slot in range(1, 14):
            self._mark(non_lockout, self.player_a, slot)
            self.assertIsNone(
                check_and_record_lockout_win(non_lockout, self.player_a))

        non_lockout.refresh_from_db()
        self.assertIsNone(non_lockout.winner_id)
        self.user_a.refresh_from_db()
        self.assertEqual(self.user_a.wins, 0)


class LockoutWinHttpTests(TestCase):
    """Drive the real /api/select endpoint to prove the win check is wired in,
    not just the helper called directly."""

    def setUp(self):
        self.user_a = User.objects.create_user(
            username="alice", email="alice@test.com", password="testpass123")
        self.user_b = User.objects.create_user(
            username="bob", email="bob@test.com", password="testpass123")
        self.room = Room.objects.create(
            name="Lockout Room", passphrase=make_password("pw"),
            hide_card=False, active=True)
        self.game = Game.from_board(
            _board(), room=self.room, seed=1,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=LockoutMode.lockout.value, fog_of_war=False)
        self.player_a = Player.objects.create(
            room=self.room, user=self.user_a, name="alice",
            role=Role.PLAYER, color_value=Color.red.value)
        self.player_b = Player.objects.create(
            room=self.room, user=self.user_b, name="bob",
            role=Role.PLAYER, color_value=Color.blue.value)

        self.client_a = Client()
        self.client_a.force_login(self.user_a)
        session = self.client_a.session
        session["authorized_rooms"] = {
            self.room.encoded_uuid: self.player_a.encoded_uuid}
        session.save()

    def test_marking_thirteen_via_api_records_the_win(self):
        for slot in range(1, 14):
            resp = self.client_a.put(
                "/api/select",
                data=json.dumps({
                    "room": self.room.encoded_uuid, "slot": slot,
                    "color": "red", "remove_color": False}),
                content_type="application/json")
            self.assertEqual(resp.status_code, 200, resp.content)

        self.game.refresh_from_db()
        self.assertEqual(self.game.winner_id, self.player_a.id)

        self.user_a.refresh_from_db()
        self.user_b.refresh_from_db()
        self.assertEqual(self.user_a.wins, 1)
        self.assertEqual(self.user_b.losses, 1)
