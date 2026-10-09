"""
The room page's AJAX calls (marking squares, choosing colors, assigning
counters) must send a CSRF token the page's JavaScript can actually see.
Production marks the csrftoken cookie HttpOnly, so the token has to come from
the page itself, not the cookie.
"""
import json
import re

from django.test import TestCase, Client, override_settings

from bingosync.models.user import User
from bingosync.models.rooms import Room, Game, Player, LockoutMode
from bingosync.models.game_type import GameType
from bingosync.models.enums import Role
from bingosync.models.colors import Color


@override_settings(CSRF_COOKIE_HTTPONLY=True)
class CsrfTokenInPageTests(TestCase):

    def setUp(self):
        self.room = Room.objects.create(
            name="R", room_code=Room.generate_room_code(),
            passphrase="", hide_card=False, active=True)
        Game.from_board([{"name": f"G{i}", "tier": 0} for i in range(1, 26)],
                        room=self.room, seed=1,
                        game_type_value=GameType.hp_cos.value,
                        lockout_mode_value=LockoutMode.non_lockout.value)
        user = User.objects.create_user(
            username="p", email="p@t.com", password="pw12345678")
        self.player = Player.objects.create(
            room=self.room, user=user, name="p",
            role=Role.PLAYER, color_value=Color.red.value)
        # Enforce CSRF the way a real browser request is checked
        self.client = Client(enforce_csrf_checks=True)
        self.client.force_login(user)
        session = self.client.session
        session["authorized_rooms"] = {
            self.room.encoded_uuid: self.player.encoded_uuid}
        session.save()

    def _mark_square(self, **headers):
        return self.client.put(
            "/api/select",
            data=json.dumps({"room": self.room.encoded_uuid, "slot": 1,
                             "color": "red", "remove_color": False}),
            content_type="application/json", **headers)

    def test_token_from_room_page_lets_a_square_be_marked(self):
        page = self.client.get(f"/room/{self.room.encoded_uuid}")
        self.assertEqual(page.status_code, 200)
        match = re.search(r'var csrftoken = "([A-Za-z0-9]+)";',
                          page.content.decode())
        self.assertIsNotNone(match, "room page doesn't embed a CSRF token")

        response = self._mark_square(HTTP_X_CSRFTOKEN=match.group(1))
        self.assertEqual(response.status_code, 200, response.content)

    def test_marking_a_square_without_a_token_is_rejected(self):
        self.client.get(f"/room/{self.room.encoded_uuid}")
        self.assertEqual(self._mark_square().status_code, 403)
