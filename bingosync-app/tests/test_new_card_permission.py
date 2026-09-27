"""
Tests for who may generate a new card: the Gamemaster always, and any Player
when the room has no Gamemaster (so a GM-less room isn't stuck on one board).
"""
import json

from django.test import TestCase, Client

from bingosync.models.user import User
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.game_type import GameType
from bingosync.models.enums import Role
from bingosync.models.colors import Color


def _board():
    return [{"name": f"G{i}", "tier": 0} for i in range(1, 26)]


class NewCardPermissionTests(TestCase):

    def _room(self):
        room = Room.objects.create(
            name="NC", room_code=Room.generate_room_code(),
            passphrase="", hide_card=False, active=True)
        Game.from_board(_board(), room=room, seed=1,
                        game_type_value=GameType.hp_cos.value,
                        lockout_mode_value=2)
        return room

    def _user(self, name):
        return User.objects.create_user(
            username=name, email=f"{name}@t.com", password="pw12345678")

    def _client_for(self, room, player):
        c = Client()
        c.force_login(player.user)
        s = c.session
        s["authorized_rooms"] = {room.encoded_uuid: player.encoded_uuid}
        s.save()
        return c

    def _post_new_card(self, client, room):
        return client.put(
            "/api/new-card",
            data=json.dumps({
                "room": room.encoded_uuid, "game_type": "50",
                "lockout_mode": "2", "seed": "",
                "hide_card": False, "fog_of_war": "off"}),
            content_type="application/json")

    def test_player_can_generate_when_no_gamemaster(self):
        room = self._room()
        player = Player.objects.create(
            room=room, user=self._user("p1"), name="p1",
            role=Role.PLAYER, color_value=Color.red.value)
        resp = self._post_new_card(self._client_for(room, player), room)
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_player_cannot_generate_when_gamemaster_present(self):
        room = self._room()
        Player.objects.create(
            room=room, user=self._user("gm"), name="gm",
            role=Role.GAMEMASTER, color_value=Color.orange.value)
        player = Player.objects.create(
            room=room, user=self._user("p1"), name="p1",
            role=Role.PLAYER, color_value=Color.red.value)
        resp = self._post_new_card(self._client_for(room, player), room)
        self.assertEqual(resp.status_code, 403, resp.content)

    def test_gamemaster_can_always_generate(self):
        room = self._room()
        gm = Player.objects.create(
            room=room, user=self._user("gm"), name="gm",
            role=Role.GAMEMASTER, color_value=Color.orange.value)
        resp = self._post_new_card(self._client_for(room, gm), room)
        self.assertEqual(resp.status_code, 200, resp.content)
