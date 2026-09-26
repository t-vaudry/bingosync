"""
Regression tests for joining a room as Player/Counter via the actual
room_view HTTP endpoint (POST /room/<uuid>).

This is distinct from tests that call JoinRoomForm.create_player() directly:
those never exercise room_view's view-level session handling, which is where
a real bug lived (_save_session_player was called with the Room instead of
the Player, causing every Player/Counter join via room code to 500).
"""
from django.test import TestCase, Client
from django.contrib.auth.hashers import make_password

from bingosync.models.user import User
from bingosync.models.rooms import Room, Game, Player
from bingosync.models.game_type import GameType
from bingosync.models.enums import Role
from bingosync.models.colors import Color


class RoomViewJoinHttpTests(TestCase):
    """Exercise the real POST /room/<uuid> join flow end to end."""

    def setUp(self):
        self.creator = User.objects.create_user(
            username='creator', email='creator@test.com', password='testpass123')
        self.room = Room.objects.create(
            name='HttpJoinRoom',
            passphrase=make_password('roompass'),
            hide_card=False,
            active=True)
        Game.objects.create(
            room=self.room, seed=1, size=5, game_type_value=GameType.hp_cos.value)
        Player.objects.create(
            room=self.room, user=self.creator, name='creator',
            role=Role.GAMEMASTER, color_value=Color.orange.value)

    def _post_join(self, client, player_name, role):
        return client.post(
            f'/room/{self.room.encoded_uuid}',
            data={
                'encoded_room_uuid': self.room.encoded_uuid,
                'player_name': player_name,
                'passphrase': 'roompass',
                'role': role,
            })

    def test_join_as_player_via_http_succeeds(self):
        """POSTing the join form as a Player must not 500 and must
        leave the session authorized to act as that player."""
        user = User.objects.create_user(
            username='httpplayer', email='p@test.com', password='testpass123')
        client = Client()
        client.force_login(user)

        response = self._post_join(client, 'httpplayer', Role.PLAYER)

        self.assertEqual(response.status_code, 302)
        player = Player.objects.get(room=self.room, name='httpplayer')
        self.assertEqual(player.role, Role.PLAYER)

        # Session must be authorized for THIS player, not the room or
        # some other player, so subsequent actions (e.g. marking a square)
        # resolve correctly instead of 403ing.
        session = client.session
        self.assertEqual(
            session['authorized_rooms'][self.room.encoded_uuid],
            player.encoded_uuid)

        # Following the redirect should render the room, not crash.
        follow_up = client.get(f'/room/{self.room.encoded_uuid}')
        self.assertEqual(follow_up.status_code, 200)

    def test_join_as_counter_via_http_succeeds(self):
        user = User.objects.create_user(
            username='httpcounter', email='c@test.com', password='testpass123')
        client = Client()
        client.force_login(user)

        response = self._post_join(client, 'httpcounter', Role.COUNTER)

        self.assertEqual(response.status_code, 302)
        player = Player.objects.get(room=self.room, name='httpcounter')
        self.assertEqual(player.role, Role.COUNTER)
        session = client.session
        self.assertEqual(
            session['authorized_rooms'][self.room.encoded_uuid],
            player.encoded_uuid)
