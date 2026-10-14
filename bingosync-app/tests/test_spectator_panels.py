"""
Spectators don't mark goals or run the room, so the room page leaves out the
color chooser and the Room Settings panel for them.
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.models.game_type import GameType

User = get_user_model()


class SpectatorPanelsTest(TestCase):

    def setUp(self):
        self.room = Room.objects.create(
            name='Test Room', room_code='TEST01', passphrase='', active=True)
        Game.from_board(
            [{"name": f"Goal {i}", "tier": 1} for i in range(25)],
            room=self.room, game_type_value=GameType.hp_cos.value,
            lockout_mode_value=1, seed=1, fog_of_war=False)

    def _page_for(self, role, user=None):
        player = Player.objects.create(
            room=self.room, user=user, name=role, role=role,
            color_value=Color.red.value)
        client = Client()
        if user:
            client.force_login(user)
        session = client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: player.encoded_uuid}
        session.save()
        return client.get(f'/room/{self.room.encoded_uuid}')

    def test_spectators_get_no_color_chooser_or_room_settings(self):
        response = self._page_for(Role.SPECTATOR)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="color-chooser"')
        self.assertNotContains(response, 'id="room-settings"')
        # Still a board to watch
        self.assertContains(response, 'id="bingo"')

    def test_players_still_get_both(self):
        user = User.objects.create_user(
            username='player1', email='p1@test.com', password='testpass123')
        response = self._page_for(Role.PLAYER, user)
        self.assertContains(response, 'id="color-chooser"')
        self.assertContains(response, 'id="room-settings"')
