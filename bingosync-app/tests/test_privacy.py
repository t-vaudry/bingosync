"""
GDPR: the privacy notice, downloading your data, deleting your account, and
no third-party font requests.
"""
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from bingosync.models.colors import Color
from bingosync.models.enums import Role
from bingosync.models.events import ChatEvent
from bingosync.models.game_type import GameType
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.user import User

PASSWORD = "pw-hermione-123"


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'privacy-tests'}})
class PrivacyTestCase(TestCase):

    def setUp(self):
        publish = patch('bingosync.publish.requests.put')
        publish.start()
        self.addCleanup(publish.stop)

        self.user = User.objects.create_user(
            username="hermione", email="hermione@test.com", password=PASSWORD)
        self.room = Room.objects.create(
            name="Library", room_code="PRIV01", passphrase="", active=True)
        Game.from_board([{"name": f"G{i}", "tier": 0} for i in range(1, 26)],
                        room=self.room, seed=1,
                        game_type_value=GameType.hp_cos.value,
                        lockout_mode_value=1)
        self.player = Player.objects.create(
            room=self.room, user=self.user, name="hermione",
            role=Role.PLAYER, color_value=Color.red.value)
        ChatEvent.objects.create(player=self.player, player_color_value=Color.red.value,
                                 body="points to Gryffindor")
        ChatEvent.objects.create(player=self.player, player_color_value=Color.red.value,
                                 body="hermione switched to the Counter role",
                                 is_system_message=True)
        self.user.current_room = self.room
        self.user.save()


class PrivacyNoticeTests(PrivacyTestCase):

    def test_notice_is_public_and_linked_from_every_page(self):
        response = self.client.get(reverse("privacy"))
        self.assertContains(response, "Privacy Notice")
        self.assertContains(self.client.get(reverse("about")), reverse("privacy"))

    def test_registration_points_to_the_notice(self):
        self.assertContains(self.client.get(reverse("register")), reverse("privacy"))

    @override_settings(PRIVACY_CONTROLLER_NAME="Tom R", PRIVACY_CONTACT_EMAIL="privacy@example.com")
    def test_shows_who_runs_the_site(self):
        response = self.client.get(reverse("privacy"))
        self.assertContains(response, "Tom R")
        self.assertContains(response, "mailto:privacy@example.com")

    @override_settings(PRIVACY_CONTROLLER_NAME="", PRIVACY_CONTACT_EMAIL="")
    def test_asks_the_operator_to_fill_in_their_details(self):
        self.assertContains(self.client.get(reverse("privacy")), "PRIVACY_CONTACT_EMAIL")

    def test_pages_load_no_fonts_from_google(self):
        page = self.client.get(reverse("landing")).content.decode()
        self.assertNotIn("googleapis", page)
        self.assertNotIn("gstatic", page)


class ExportTests(PrivacyTestCase):

    def test_download_your_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("export_account"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        data = response.json()
        self.assertEqual(data["account"]["email"], "hermione@test.com")
        self.assertEqual(data["rooms"][0]["room"], "Library")
        self.assertEqual([m["text"] for m in data["chat_messages"]], ["points to Gryffindor"])

    def test_requires_login(self):
        response = self.client.get(reverse("export_account"))
        self.assertEqual(response.status_code, 302)


class DeleteAccountTests(PrivacyTestCase):

    def _delete(self, password=PASSWORD):
        self.client.force_login(self.user)
        return self.client.post(reverse("delete_account"), {"password": password})

    def test_deleting_removes_account_name_and_chat(self):
        response = self._delete()
        self.assertRedirects(response, reverse("landing") + "?account_deleted=1",
                             fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(username="hermione").exists())

        self.player.refresh_from_db()
        self.assertIsNone(self.player.user)
        self.assertEqual(self.player.name, "deleted player")
        self.assertFalse(self.player.connected)
        self.assertFalse(ChatEvent.objects.filter(body="points to Gryffindor").exists())

    def test_logged_out_afterwards(self):
        self._delete()
        response = self.client.get(reverse("export_account"))
        self.assertEqual(response.status_code, 302)

    def test_wrong_password_deletes_nothing(self):
        response = self._delete(password="wrong")
        self.assertIn("delete_error=1", response["Location"])
        self.assertTrue(User.objects.filter(username="hermione").exists())

    def test_must_be_posted(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("delete_account")).status_code, 405)

    def test_delete_controls_only_on_your_own_profile(self):
        other = User.objects.create_user(username="ron", email="ron@test.com")
        self.client.force_login(self.user)
        own = reverse("user_profile", kwargs={"username": "hermione"})
        theirs = reverse("user_profile", kwargs={"username": "ron"})
        self.assertContains(self.client.get(own), reverse("delete_account"))
        self.assertNotContains(self.client.get(theirs), reverse("delete_account"))
