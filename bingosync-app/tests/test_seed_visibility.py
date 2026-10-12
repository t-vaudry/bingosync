"""
The seed in a room run by a Gamemaster is only sent to the Gamemaster and
counters: not to players, spectators, or the public stream overlay and Room
History. Without a Gamemaster everyone sees it.
"""
import json
from unittest.mock import patch

from django.test import TestCase, Client

from bingosync.models.user import User
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.models.game_type import GameType
from bingosync.models.events import NewCardEvent
from bingosync.publish import publish_new_card_event

SEED = 424242


class SeedVisibilityTests(TestCase):

    def setUp(self):
        self.room = Room.objects.create(
            name="Seed Room", room_code="SEED01", passphrase="",
            hide_card=False, active=True)
        Game.from_board([{"name": f"G{i}", "tier": 0} for i in range(1, 26)],
                        room=self.room, seed=SEED,
                        game_type_value=GameType.hp_cos.value,
                        lockout_mode_value=1)
        self.gm = self._join("gm", Role.GAMEMASTER, Color.orange)
        self.player = self._join("player", Role.PLAYER, Color.red)
        self.counter = self._join("counter", Role.COUNTER, Color.blue)
        self.spectator = self._join("spectator", Role.SPECTATOR, Color.green)

    def _join(self, name, role, color):
        user = User.objects.create_user(
            username=name, email=f"{name}@t.com", password="pw12345678")
        return Player.objects.create(
            room=self.room, user=user, name=name, role=role,
            color_value=color.value)

    def _client(self, player):
        client = Client()
        client.force_login(player.user)
        session = client.session
        session["authorized_rooms"] = {self.room.encoded_uuid: player.encoded_uuid}
        session.save()
        return client

    def _page(self, player):
        response = self._client(player).get(f"/room/{self.room.encoded_uuid}")
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def _settings(self, player):
        response = self._client(player).get(
            f"/room/{self.room.encoded_uuid}/room-settings")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_player_and_spectator_get_no_seed_under_a_gamemaster(self):
        for viewer in (self.player, self.spectator):
            self.assertNotIn(str(SEED), self._page(viewer), viewer.name)
            data = self._settings(viewer)
            self.assertIsNone(data["settings"]["seed"], viewer.name)
            self.assertNotIn(str(SEED), data["panel"], viewer.name)

    def test_gamemaster_and_counter_get_the_seed(self):
        for viewer in (self.gm, self.counter):
            self.assertIn(str(SEED), self._page(viewer), viewer.name)
            self.assertEqual(self._settings(viewer)["settings"]["seed"], SEED,
                             viewer.name)

    def test_everyone_gets_the_seed_without_a_gamemaster(self):
        self.gm.role = Role.PLAYER
        self.gm.save()
        self.assertIn(str(SEED), self._page(self.player))
        self.assertEqual(self._settings(self.player)["settings"]["seed"], SEED)

    def test_settings_endpoint_hides_seed_from_outsiders(self):
        response = Client().get(f"/room/{self.room.encoded_uuid}/room-settings")
        self.assertIsNone(response.json()["settings"]["seed"])

    def test_chat_history_hides_new_card_seed_from_player(self):
        NewCardEvent.objects.create(
            player=self.gm, player_color_value=Color.orange.value,
            game_type_value=GameType.hp_cos.value, seed=SEED)

        def new_card_seeds(viewer):
            response = self._client(viewer).get(
                f"/room/{self.room.encoded_uuid}/feed?full=true")
            return [e["seed"] for e in response.json()["events"]
                    if e["type"] == "new-card"]

        self.assertEqual(new_card_seeds(self.player), [None])
        self.assertEqual(new_card_seeds(self.counter), [SEED])

    def test_new_card_broadcast_omits_seed_under_a_gamemaster(self):
        event = NewCardEvent.objects.create(
            player=self.gm, player_color_value=Color.orange.value,
            game_type_value=GameType.hp_cos.value, seed=SEED)
        with patch("bingosync.publish._publish_json") as publish:
            publish_new_card_event(event)
        self.assertIsNone(publish.call_args[0][0]["seed"])

        self.gm.role = Role.PLAYER
        self.gm.save()
        with patch("bingosync.publish._publish_json") as publish:
            publish_new_card_event(event)
        self.assertEqual(publish.call_args[0][0]["seed"], SEED)

    def test_stream_overlay_hides_seed(self):
        response = Client().get(f"/room/{self.room.encoded_uuid}/stream")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(SEED), response.content.decode())

    def test_room_history_hides_seed_while_gamemaster_room_is_active(self):
        response = Client().get("/history")
        self.assertContains(response, "Seed Room")
        self.assertNotContains(response, str(SEED))

        self.room.active = False
        self.room.save()
        self.assertContains(Client().get("/history"), str(SEED))
