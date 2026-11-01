"""
GET /api/room/<uuid>: a public, anonymous, read-only view of a room.
"""
import json

from django.core.cache import cache
from django.test import TestCase, Client

from bingosync.models.colors import Color
from bingosync.models.enums import Role
from bingosync.models.game_type import GameType
from bingosync.models.rooms import Room, Game, Player, CounterTally

SEED = 424242
PASSPHRASE = "s3cretpass"


class PublicApiTests(TestCase):

    def setUp(self):
        cache.clear()
        self.room = Room.objects.create(
            name="Public Room", room_code="PUB001", passphrase=PASSPHRASE,
            hide_card=False, active=True)
        board = [{"name": f"G{i}", "tier": 0} for i in range(1, 26)]
        board[0] = {"name": "Throw 3 gnomes", "tier": 1, "goal_key": "g",
                    "amount": 3, "unique_amount": 3, "triggers": []}
        self.game = Game.from_board(
            board, room=self.room, seed=SEED,
            game_type_value=GameType.hp_cos.value, lockout_mode_value=1)
        self.player = self._player("runner", Role.PLAYER, Color.red)
        self.counter = self._player("counter1", Role.COUNTER, Color.blue)
        self.counter.monitoring_color_value = Color.red.value
        self.counter.save()
        self.url = f"/api/room/{self.room.encoded_uuid}"

    def _player(self, name, role, color):
        return Player.objects.create(
            room=self.room, name=name, role=role, color_value=color.value)

    def _get(self):
        response = Client().get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _mark(self, slot, color, status="confirmed"):
        square = self.game.squares[slot - 1]
        sq_color = square.color
        sq_color.add(color)
        square.color = sq_color
        square.claim_status = status
        square.claimed_by = self.player
        square.save()

    def test_anonymous_read_of_the_room(self):
        data = self._get()
        self.assertEqual(data["room"]["name"], "Public Room")
        self.assertEqual(data["room"]["lockout_mode"], "Non-Lockout")
        self.assertTrue(data["room"]["active"])
        self.assertIsNone(data["room"]["winner"])
        self.assertEqual(data["card"]["size"], 5)
        self.assertEqual(len(data["card"]["squares"]), 25)
        self.assertEqual(data["card"]["squares"][0]["name"], "Throw 3 gnomes")
        self.assertEqual({p["name"] for p in data["players"]},
                         {"runner", "counter1"})

    def test_scores_squares_and_lines(self):
        for slot in (1, 2, 3, 4, 5):
            self._mark(slot, Color.red)
        self._mark(6, Color.red, status="rejected")
        data = self._get()
        self.assertEqual(data["scores"]["red"], {"squares": 5, "lines": 1})

    def test_counter_counts_are_listed_per_counter(self):
        second = self._player("counter2", Role.COUNTER, Color.green)
        second.monitoring_color_value = Color.red.value
        second.save()
        CounterTally.objects.create(
            game=self.game, counter=self.counter,
            color_value=Color.red.value, counts={"1": 2})
        data = self._get()
        by_name = {c["name"]: c for c in data["counters"]}
        self.assertEqual(set(by_name), {"counter1", "counter2"})
        self.assertEqual(by_name["counter1"]["color"], "red")
        self.assertEqual(by_name["counter1"]["goals"],
                         [{"slot": 1, "count": 2, "amount": 3}])
        self.assertEqual(by_name["counter2"]["goals"][0]["count"], 0)

    def test_seed_hidden_while_active_under_a_gamemaster(self):
        self.assertEqual(self._get()["room"]["seed"], SEED)
        self._player("gm", Role.GAMEMASTER, Color.orange)
        self.assertIsNone(self._get()["room"]["seed"])
        self.room.active = False
        self.room.save()
        self.assertEqual(self._get()["room"]["seed"], SEED)

    def test_hidden_card_leaves_out_squares_seed_and_counter_goals(self):
        self.room.hide_card = True
        self.room.save()
        data = self._get()
        self.assertIsNone(data["card"])
        self.assertIsNone(data["room"]["seed"])
        self.assertTrue(data["room"]["card_hidden"])
        self.assertEqual(data["counters"][0]["goals"], [])

    def test_nothing_sensitive_leaks(self):
        CounterTally.objects.create(
            game=self.game, counter=self.counter,
            color_value=Color.red.value, counts={"1": 1},
            saved_counts={"1": 2}, dismissed=[1])
        body = Client().get(self.url).content.decode()
        for secret in (PASSPHRASE, self.player.encoded_uuid,
                       str(self.player.uuid), self.counter.encoded_uuid,
                       "saved_counts", "dismissed", "socket"):
            self.assertNotIn(secret, body)

    def test_post_not_allowed_and_unknown_room_404(self):
        self.assertEqual(Client().post(self.url).status_code, 405)
        self.assertEqual(Client().get("/api/room/nonsense").status_code, 404)
