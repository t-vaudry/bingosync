"""
Tests for the lifetime stat counters: total_squares_marked (per confirmed
mark) and total_games_played (per completed game, credited on new card).
"""
import json

from django.test import TestCase, Client

from bingosync.models.user import User
from bingosync.models.rooms import Room, Game, Player, LockoutMode
from bingosync.models.game_type import GameType
from bingosync.models.enums import Role
from bingosync.models.colors import Color


def _board():
    return [{"name": f"G{i}", "tier": 0} for i in range(1, 26)]


class StatCounterTests(TestCase):

    def _user(self, name):
        return User.objects.create_user(
            username=name, email=f"{name}@t.com", password="pw12345678")

    def _room(self, lockout=LockoutMode.lockout):
        room = Room.objects.create(
            name="S", room_code=Room.generate_room_code(),
            passphrase="", hide_card=False, active=True)
        Game.from_board(_board(), room=room, seed=1,
                        game_type_value=GameType.hp_cos.value,
                        lockout_mode_value=lockout.value)
        return room

    def _client(self, room, player):
        c = Client()
        c.force_login(player.user)
        s = c.session
        s["authorized_rooms"] = {room.encoded_uuid: player.encoded_uuid}
        s.save()
        return c

    def test_squares_marked_increments_per_confirmed_mark(self):
        room = self._room()
        p = Player.objects.create(
            room=room, user=self._user("a"), name="a",
            role=Role.PLAYER, color_value=Color.red.value)
        client = self._client(room, p)
        for slot in range(1, 4):
            resp = client.put(
                "/api/select",
                data=json.dumps({"room": room.encoded_uuid, "slot": slot,
                                 "color": "red", "remove_color": False}),
                content_type="application/json")
            self.assertEqual(resp.status_code, 200, resp.content)
        p.user.refresh_from_db()
        self.assertEqual(p.user.total_squares_marked, 3)

    def test_games_played_credited_to_players_on_new_card(self):
        room = self._room()
        a = Player.objects.create(
            room=room, user=self._user("a"), name="a",
            role=Role.PLAYER, color_value=Color.red.value)
        b = Player.objects.create(
            room=room, user=self._user("b"), name="b",
            role=Role.PLAYER, color_value=Color.blue.value)
        # A logged-in spectator must NOT be credited a game played.
        spectator = Player.objects.create(
            room=room, user=self._user("spec"), name="spec",
            role=Role.SPECTATOR, color_value=Color.blue.value)

        client = self._client(room, a)  # A can generate (no gamemaster present)
        resp = client.put(
            "/api/new-card",
            data=json.dumps({"room": room.encoded_uuid, "game_type": "50",
                             "lockout_mode": "2", "seed": "",
                             "hide_card": False, "fog_of_war": "off"}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200, resp.content)

        a.user.refresh_from_db()
        b.user.refresh_from_db()
        spectator.user.refresh_from_db()
        self.assertEqual(a.user.total_games_played, 1)
        self.assertEqual(b.user.total_games_played, 1)
        self.assertEqual(spectator.user.total_games_played, 0)
