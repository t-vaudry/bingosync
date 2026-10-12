"""
The room join page (reached from a shared room link) must have a single
<form> with the "Join Room" button inside it. A nested form rendered by
crispy used to end the page's form early, so the button submitted nothing.
"""
from django.test import TestCase

from bingosync.models.rooms import Room, Game
from bingosync.models.game_type import GameType


class JoinPageFormTests(TestCase):

    def test_join_button_is_inside_the_only_form(self):
        room = Room.objects.create(
            name="Join Me", room_code="JOIN01", passphrase="",
            hide_card=False, active=True)
        Game.from_board([{"name": f"G{i}", "tier": 0} for i in range(1, 26)],
                        room=room, seed=1, game_type_value=GameType.hp_cos.value,
                        lockout_mode_value=1)

        html = self.client.get(f"/room/{room.encoded_uuid}").content.decode()

        self.assertEqual(html.count("<form"), 1)
        form = html[html.index("<form"):html.index("</form>")]
        self.assertIn('value="Join Room"', form)
