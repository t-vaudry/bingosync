"""
Leaving and rejoining a room, picking your own role when there's no
Gamemaster, and the counter's review-style preference.
"""
import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from bingosync.models.colors import Color
from bingosync.models.enums import Role
from bingosync.models.events import ConnectionEvent, ChatEvent
from bingosync.models.game_type import GameType
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.user import User, ReviewStyle
from bingosync.forms import JoinRoomForm


@override_settings(CACHES={'default': {
    'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    'LOCATION': 'leaving-and-roles'}})
class RoomTestCase(TestCase):

    def setUp(self):
        publish = patch('bingosync.publish.requests.put')
        publish.start()
        self.addCleanup(publish.stop)
        self.room = Room.objects.create(
            name="R", room_code="LEAVE1", passphrase="", active=True)
        Game.from_board([{"name": f"G{i}", "tier": 0} for i in range(1, 26)],
                        room=self.room, seed=1,
                        game_type_value=GameType.hp_cos.value,
                        lockout_mode_value=1)
        self.user = User.objects.create_user(username="harry", email="harry@test.com", password="pw-harry-123")

    def _sit_in_room(self, player):
        session = self.client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: player.encoded_uuid}
        session.save()

    def _player(self, user=None, role=Role.PLAYER, name="harry"):
        return Player.objects.create(room=self.room, user=user, name=name,
                                     role=role, color_value=Color.red.value)

    def _join(self, role=Role.PLAYER):
        form = JoinRoomForm(data={
            'encoded_room_uuid': self.room.encoded_uuid,
            'player_name': 'harry',
            'passphrase': '',
            'role': role,
        }, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        return form.create_player(user=self.user)


class LeavingTests(RoomTestCase):

    def test_disconnect_button_leaves_the_room_at_once(self):
        player = self._player(self.user)
        self.client.force_login(self.user)
        self._sit_in_room(player)

        self.client.get(reverse('room_disconnect', kwargs={
            'encoded_room_uuid': self.room.encoded_uuid}))

        player.refresh_from_db()
        self.assertFalse(player.connected)
        self.assertNotIn(player, self.room.connected_players)

    def test_websocket_report_after_leaving_is_not_recorded_again(self):
        player = self._player(self.user)
        self.client.force_login(self.user)
        self._sit_in_room(player)
        self.client.get(reverse('room_disconnect', kwargs={
            'encoded_room_uuid': self.room.encoded_uuid}))

        from django.conf import settings
        self.client.get(f"/api/disconnected/{player.encoded_uuid}",
                        HTTP_X_INTERNAL_SECRET=settings.INTERNAL_API_SECRET)
        self.assertEqual(ConnectionEvent.objects.filter(
            player=player, event=2).count(), 1)

    def test_rejoining_gets_your_player_back(self):
        first = self._join()
        first.update_color(Color.green)
        ConnectionEvent.atomically_disconnect(first)

        again = self._join()
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(Player.objects.filter(room=self.room, user=self.user).count(), 1)
        self.assertEqual(again.color, Color.green)

    def test_rejoining_as_another_role_switches_role(self):
        first = self._join(Role.COUNTER)
        Player.objects.filter(pk=first.pk).update(monitoring_color_value=Color.red.value)

        again = self._join(Role.PLAYER)
        self.assertEqual(again.pk, first.pk)
        self.assertEqual(again.role, Role.PLAYER)
        self.assertIsNone(again.monitoring_color_value)

    def test_rejoining_gamemaster_stays_gamemaster(self):
        gm = self._player(self.user, role=Role.GAMEMASTER)
        again = self._join(Role.PLAYER)
        self.assertEqual(again.pk, gm.pk)
        self.assertEqual(again.role, Role.GAMEMASTER)

    def test_room_page_works_after_rejoining(self):
        player = self._join()
        self.client.force_login(self.user)
        self._sit_in_room(player)
        response = self.client.get(reverse('room_view', kwargs={
            'encoded_room_uuid': self.room.encoded_uuid}))
        self.assertEqual(response.status_code, 200)


class OwnRoleTests(RoomTestCase):

    def _change_own_role(self, player, new_role):
        self._sit_in_room(player)
        return self.client.post('/api/assign-role', data=json.dumps({
            'room': self.room.encoded_uuid,
            'target_player_uuid': player.encoded_uuid,
            'new_role': new_role,
        }), content_type='application/json')

    def test_without_a_gamemaster_you_pick_your_own_role(self):
        player = self._player(self.user)
        response = self._change_own_role(player, Role.COUNTER)
        self.assertEqual(response.status_code, 200)
        player.refresh_from_db()
        self.assertEqual(player.role, Role.COUNTER)
        self.assertTrue(ChatEvent.objects.filter(
            body="harry switched to the Counter role").exists())

    def test_with_a_gamemaster_only_they_assign_roles(self):
        self._player(role=Role.GAMEMASTER, name="gm")
        player = self._player(self.user)
        response = self._change_own_role(player, Role.COUNTER)
        self.assertEqual(response.status_code, 403)

    def test_cannot_change_someone_elses_role(self):
        player = self._player(self.user)
        other = self._player(User.objects.create_user(username="ron", email="ron@test.com"), name="ron")
        self._sit_in_room(player)
        response = self.client.post('/api/assign-role', data=json.dumps({
            'room': self.room.encoded_uuid,
            'target_player_uuid': other.encoded_uuid,
            'new_role': Role.SPECTATOR,
        }), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_spectator_without_an_account_stays_a_spectator(self):
        spectator = self._player(role=Role.SPECTATOR, name="anon")
        response = self._change_own_role(spectator, Role.PLAYER)
        self.assertEqual(response.status_code, 400)

    def test_cannot_make_yourself_gamemaster(self):
        player = self._player(self.user)
        response = self._change_own_role(player, Role.GAMEMASTER)
        self.assertEqual(response.status_code, 400)

    def test_role_picker_only_shown_without_a_gamemaster(self):
        player = self._player(self.user)
        self.client.force_login(self.user)
        self._sit_in_room(player)
        url = reverse('room_view', kwargs={'encoded_room_uuid': self.room.encoded_uuid})
        self.assertContains(self.client.get(url), 'id="own-role-select"')

        self._player(role=Role.GAMEMASTER, name="gm")
        self.assertNotContains(self.client.get(url), 'id="own-role-select"')


class ReviewStylePreferenceTests(RoomTestCase):

    def _profile_url(self, user):
        return reverse('user_profile', kwargs={'username': user.username})

    def test_defaults_to_the_review_list(self):
        self.assertEqual(self.user.review_style, ReviewStyle.LIST)

    def test_save_your_own_preference(self):
        self.client.force_login(self.user)
        response = self.client.post(self._profile_url(self.user),
                                    {'review_style': ReviewStyle.BUTTONS})
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.review_style, ReviewStyle.BUTTONS)

    def test_preferences_only_on_your_own_profile(self):
        other = User.objects.create_user(username="ron", email="ron@test.com")
        self.client.force_login(self.user)
        self.assertContains(self.client.get(self._profile_url(self.user)), 'name="review_style"')
        self.assertNotContains(self.client.get(self._profile_url(other)), 'name="review_style"')

        response = self.client.post(self._profile_url(other),
                                    {'review_style': ReviewStyle.CLICK})
        self.assertEqual(response.status_code, 403)
        other.refresh_from_db()
        self.assertEqual(other.review_style, ReviewStyle.LIST)

    def test_unknown_style_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(self._profile_url(self.user), {'review_style': 'nope'})
        self.assertEqual(response.status_code, 400)

    def test_counter_page_uses_the_preference(self):
        self.user.review_style = ReviewStyle.HOVER
        self.user.save()
        counter = self._player(self.user, role=Role.COUNTER)
        self.client.force_login(self.user)
        self._sit_in_room(counter)
        response = self.client.get(reverse('room_view', kwargs={
            'encoded_room_uuid': self.room.encoded_uuid}))
        self.assertContains(response, 'playersPanel, "hover")')
