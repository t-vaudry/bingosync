"""
Tests for optional room passwords: a room can be created without one, and a
password is only required to join when the room actually has one.
"""
from django.test import TestCase
from django.contrib.auth import hashers

from bingosync.models.user import User
from bingosync.models.enums import Role
from bingosync.forms import RoomForm, JoinRoomForm


class RoomPasswordOptionalTests(TestCase):

    def setUp(self):
        self.creator = User.objects.create_user(
            username="creator", email="c@t.com", password="pw12345678")

    def _room_data(self, passphrase):
        return {
            "room_name": "A Room",
            "passphrase": passphrase,
            "game_type": "50",
            "lockout_mode": "1",
            "seed": "12345",
            "hide_card": False,
            "fog_of_war": False,
        }

    def _make_room(self, passphrase):
        form = RoomForm(data=self._room_data(passphrase), user=self.creator)
        self.assertTrue(form.is_valid(), form.errors)
        return form.create_room(user=self.creator)

    def _join_form(self, room, passphrase):
        joiner = User.objects.create_user(
            username="joiner", email="j@t.com", password="pw12345678")
        return JoinRoomForm(data={
            "encoded_room_uuid": room.encoded_uuid,
            "player_name": "joiner",
            "passphrase": passphrase,
            "role": Role.PLAYER,
        }, room=room, user=joiner)

    def test_create_without_password_stores_empty(self):
        room = self._make_room("")
        self.assertEqual(room.passphrase, "")

    def test_create_with_password_stores_hash(self):
        room = self._make_room("secret")
        self.assertNotEqual(room.passphrase, "")
        self.assertTrue(hashers.check_password("secret", room.passphrase))

    def test_join_open_room_without_password(self):
        room = self._make_room("")
        form = self._join_form(room, "")
        self.assertTrue(form.is_valid(), form.errors)

    def test_join_protected_room_rejects_blank_password(self):
        room = self._make_room("secret")
        form = self._join_form(room, "")
        self.assertFalse(form.is_valid())

    def test_join_protected_room_accepts_correct_password(self):
        room = self._make_room("secret")
        form = self._join_form(room, "secret")
        self.assertTrue(form.is_valid(), form.errors)
