import json

from django import test
from django.contrib.auth import get_user_model
from django.test import override_settings

from bingosync import models
from bingosync.models.events import ConnectionEvent
from bingosync.models.rooms import CardReveal
from bingosync.obs import obs_target, board_hidden_for, obs_state

User = get_user_model()


@override_settings(
    CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-test-cache-obs'}},
    RATELIMIT_ENABLE=False)
class ObsTestCase(test.TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='streamer', email='s@example.com', password='x')
        self.client.force_login(self.user)

    def make_room(self, name, hide_card=False):
        resp = self.client.post("/", {
            "room_name": name,
            "passphrase": "pw",
            "game_type": str(models.GameType.hp_cos.value),
            "lockout_mode": str(models.LockoutMode.lockout.value),
            "hide_card": "on" if hide_card else "",
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        return resp.context["room"]

    def target_room_id(self):
        self.user.refresh_from_db()
        return obs_target(self.user).room_id

    def player_in(self, room):
        return models.Player.objects.get(room=room, user=self.user)

    def test_can_be_in_several_rooms(self):
        first = self.make_room("One")
        second = self.make_room("Two")
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(
            models.Player.objects.filter(user=self.user).count(), 2)

    def test_token_resolves_to_users_room(self):
        room = self.make_room("One")
        token = self.user.ensure_obs_token()
        resp = self.client.get("/obs/" + token)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["room"].id, room.id)
        # Includes the in-review styling, and has no headers to hide via JS
        self.assertContains(resp, "claim-status.css")

    def test_unknown_token_404s(self):
        self.assertEqual(test.Client().get("/obs/nope").status_code, 404)
        self.assertEqual(test.Client().get("/obs/nope/state").status_code, 404)

    def test_idle_when_in_no_room(self):
        token = self.user.ensure_obs_token()
        resp = test.Client().get("/obs/" + token)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context["player"])
        state = test.Client().get("/obs/" + token + "/state").json()
        self.assertIsNone(state["room"])

    def test_regenerate_invalidates_old_token(self):
        self.make_room("One")
        old = self.user.ensure_obs_token()
        resp = self.client.post("/api/obs/regenerate", "{}",
                                content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.obs_token, old)
        self.assertEqual(test.Client().get("/obs/" + old).status_code, 404)
        self.assertEqual(
            test.Client().get(resp.json()["url"]).status_code, 200)

    def test_chosen_room_wins_when_in_several(self):
        first = self.make_room("One")
        second = self.make_room("Two")
        # Making a second room doesn't take the link over from the first
        self.assertEqual(self.target_room_id(), first.id)
        resp = self.client.post(
            "/api/obs/room",
            json.dumps({"room": second.encoded_uuid, "selected": True}),
            content_type="application/json")
        self.assertEqual(resp.json()["selected"], True)
        self.user.refresh_from_db()
        self.assertEqual(self.target_room_id(), second.id)
        resp = self.client.post(
            "/api/obs/room",
            json.dumps({"room": first.encoded_uuid, "selected": True}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.target_room_id(), first.id)
        # Unticking hands the link to the other live room
        resp = self.client.post(
            "/api/obs/room",
            json.dumps({"room": first.encoded_uuid, "selected": False}),
            content_type="application/json")
        self.assertEqual(resp.json()["selected"], False)
        self.user.refresh_from_db()
        self.assertEqual(self.target_room_id(), second.id)

    def test_new_room_does_not_steal_a_live_source(self):
        first = self.make_room("One")
        self.make_room("Two")
        self.make_room("Three")
        self.assertEqual(self.target_room_id(), first.id)

    def test_checkbox_ticked_only_in_the_source_room(self):
        first = self.make_room("One")
        second = self.make_room("Two")
        box = 'id="obs-room-toggle" type="checkbox" data-room="%s" checked'
        on_first = self.client.get(first.get_absolute_url())
        on_second = self.client.get(second.get_absolute_url())
        self.assertContains(on_first, box % first.encoded_uuid)
        self.assertNotContains(on_second, box % second.encoded_uuid)

    def test_source_moves_on_when_its_room_ends(self):
        first = self.make_room("One")
        second = self.make_room("Two")
        ConnectionEvent.make_disconnected_event(self.player_in(first)).save()
        first.update_active()
        self.assertEqual(self.target_room_id(), second.id)

    def test_cannot_choose_a_room_you_are_not_in(self):
        other = User.objects.create_user(
            username='other', email='o@example.com', password='x')
        c = test.Client()
        c.force_login(other)
        room = self.make_room("Mine")
        resp = c.post(
            "/api/obs/room",
            json.dumps({"room": room.encoded_uuid, "selected": True}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 403)

    def test_hidden_state_is_per_player(self):
        room = self.make_room("Hidden", hide_card=True)
        mine = self.player_in(room)
        other_user = User.objects.create_user(
            username='other', email='o@example.com', password='x')
        theirs = models.Player.objects.create(
            room=room, name="other", user=other_user)
        self.assertTrue(board_hidden_for(mine))
        self.assertTrue(board_hidden_for(theirs))
        CardReveal.objects.create(player=theirs, game=room.current_game)
        self.assertTrue(board_hidden_for(mine))
        self.assertFalse(board_hidden_for(theirs))
        CardReveal.objects.create(player=mine, game=room.current_game)
        self.assertFalse(board_hidden_for(mine))
        self.assertFalse(obs_state(self.user)["hidden"])

    def test_page_has_cover_only_while_hidden(self):
        room = self.make_room("Hidden", hide_card=True)
        token = self.user.ensure_obs_token()
        resp = test.Client().get("/obs/" + token)
        self.assertContains(resp, 'class="board-cover"')
        CardReveal.objects.create(
            player=self.player_in(room), game=room.current_game)
        resp = test.Client().get("/obs/" + token)
        self.assertNotContains(resp, 'class="board-cover"')

    def test_room_page_links_permanent_obs_url(self):
        room = self.make_room("One")
        resp = self.client.get(room.get_absolute_url())
        token = User.objects.get(pk=self.user.pk).obs_token
        self.assertIsNotNone(token)
        self.assertContains(resp, 'data-url="/obs/%s"' % token)

    def test_player_can_reveal_their_own_card_over_http(self):
        # Players can't use the Gamemaster-only /api/revealed, so the room
        # page tells the server about their own reveal separately.
        room = self.make_room("Hidden", hide_card=True)
        token = self.user.ensure_obs_token()
        url = "/obs/%s/state" % token
        self.assertTrue(test.Client().get(url).json()["hidden"])
        resp = self.client.post(
            "/api/card-revealed", json.dumps({"room": room.encoded_uuid}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(test.Client().get(url).json()["hidden"])
        # It is personal: the room's seed/card visibility is unchanged
        self.assertTrue(room.is_seed_hidden)
        # Repeating it is harmless
        self.client.post(
            "/api/card-revealed", json.dumps({"room": room.encoded_uuid}),
            content_type="application/json")
        self.assertEqual(CardReveal.objects.count(), 1)

    def test_new_card_covers_again(self):
        room = self.make_room("Hidden", hide_card=True)
        player = self.player_in(room)
        CardReveal.objects.create(player=player, game=room.current_game)
        self.assertFalse(board_hidden_for(player))
        models.Game.from_board(
            room.current_game.board, room=room,
            game_type_value=room.current_game.game_type_value,
            lockout_mode_value=room.current_game.lockout_mode.value,
            seed="2", fog_of_war=False)
        self.assertTrue(board_hidden_for(models.Player.objects.get(pk=player.pk)))

    def test_gamemaster_reveal_uncovers_everyone(self):
        from bingosync.models.events import RevealedEvent
        room = self.make_room("Hidden", hide_card=True)
        mine = self.player_in(room)
        self.assertTrue(board_hidden_for(mine))
        gm = models.Player.objects.create(
            room=room, name="gm", role="gamemaster")
        RevealedEvent.objects.create(
            player=gm, player_color_value=gm.color.value)
        self.assertFalse(board_hidden_for(mine))
        self.assertFalse(obs_state(self.user)["hidden"])

    def test_room_page_cover_matches_obs_state(self):
        room = self.make_room("Hidden", hide_card=True)
        resp = self.client.get(room.get_absolute_url())
        self.assertContains(resp, 'board-container hidden-card')
        self.client.post(
            "/api/card-revealed", json.dumps({"room": room.encoded_uuid}),
            content_type="application/json")
        resp = self.client.get(room.get_absolute_url())
        self.assertNotContains(resp, 'board-container hidden-card')
        self.assertFalse(obs_state(self.user)["hidden"])

    def test_card_reveal_needs_a_joined_player(self):
        room = self.make_room("Hidden", hide_card=True)
        resp = test.Client().post(
            "/api/card-revealed", json.dumps({"room": room.encoded_uuid}),
            content_type="application/json")
        self.assertIn(resp.status_code, (401, 403, 404))
        self.assertEqual(CardReveal.objects.count(), 0)


@override_settings(RATELIMIT_ENABLE=False)
class AnonymousObsTestCase(test.TestCase):
    """People without an account get an OBS link for their room."""

    def setUp(self):
        self.client = test.Client()
        self.owner = User.objects.create_user(
            username='owner', email='o@example.com', password='x')
        c = test.Client()
        c.force_login(self.owner)
        resp = c.post("/", {
            "room_name": "R", "passphrase": "", "game_type":
            str(models.GameType.hp_cos.value),
            "lockout_mode": str(models.LockoutMode.lockout.value),
            "hide_card": "on"}, follow=True)
        self.room = resp.context["room"]
        join = self.client.post("/api/join-room", json.dumps({
            "room": self.room.encoded_uuid, "nickname": "guest",
            "password": "", "role": "spectator"}),
            content_type="application/json")
        self.assertEqual(join.status_code, 200, join.content)

    def test_anonymous_player_gets_working_obs_link(self):
        resp = self.client.get(self.room.get_absolute_url())
        self.assertContains(resp, 'id="copy-obs-link"')
        player = models.Player.objects.get(room=self.room, name="guest")
        self.assertIsNotNone(player.obs_token)
        self.assertContains(resp, 'data-url="/obs/%s"' % player.obs_token)
        obs = test.Client().get("/obs/" + player.obs_token)
        self.assertEqual(obs.status_code, 200)
        self.assertEqual(obs.context["room"].id, self.room.id)
        self.assertContains(obs, 'class="board-cover"')

    def test_anonymous_link_goes_dead_once_they_disconnect(self):
        player = models.Player.objects.get(room=self.room, name="guest")
        token = player.ensure_obs_token()
        self.assertEqual(
            test.Client().get("/obs/" + token + "/state").json()["room"],
            self.room.encoded_uuid)
        ConnectionEvent.make_disconnected_event(player).save()
        self.assertIsNone(
            test.Client().get("/obs/" + token + "/state").json()["room"])
        self.assertIsNone(test.Client().get("/obs/" + token).context["player"])

    def test_anonymous_regenerate(self):
        self.client.get(self.room.get_absolute_url())
        player = models.Player.objects.get(room=self.room, name="guest")
        old = player.obs_token
        resp = self.client.post(
            "/api/obs/regenerate",
            json.dumps({"room": self.room.encoded_uuid}),
            content_type="application/json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(test.Client().get("/obs/" + old).status_code, 404)
        self.assertEqual(
            test.Client().get(resp.json()["url"]).status_code, 200)


@override_settings(
    CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-test-cache-obs-stars'}},
    RATELIMIT_ENABLE=False)
class StarTestCase(test.TestCase):
    """Stars a player puts on goals also show in their OBS source."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='starry', email='st@example.com', password='x')
        self.client.force_login(self.user)
        resp = self.client.post("/", {
            "room_name": "S", "passphrase": "pw",
            "game_type": str(models.GameType.hp_cos.value),
            "lockout_mode": str(models.LockoutMode.lockout.value),
        }, follow=True)
        self.room = resp.context["room"]

    def star(self, slot, starred=True):
        return self.client.post(
            "/api/star",
            json.dumps({"room": self.room.encoded_uuid, "slot": slot,
                        "starred": starred}),
            content_type="application/json")

    def test_stars_show_in_obs_state_and_room_page(self):
        self.assertEqual(self.star(3).status_code, 200)
        self.assertEqual(self.star(7).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(obs_state(self.user)["stars"], [3, 7])
        self.assertEqual(self.star(3, False).status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(obs_state(self.user)["stars"], [7])
        page = self.client.get(self.room.get_absolute_url())
        self.assertEqual(page.context["starred_slots"], [7])

    def test_obs_page_carries_the_stars(self):
        self.star(5)
        token = self.user.ensure_obs_token()
        resp = test.Client().get("/obs/" + token)
        self.assertEqual(resp.context["starred_slots"], [5])

    def test_bad_slot_rejected(self):
        self.assertEqual(self.star(999).status_code, 400)

    def test_must_be_in_the_room(self):
        outsider = test.Client()
        resp = outsider.post(
            "/api/star",
            json.dumps({"room": self.room.encoded_uuid, "slot": 1,
                        "starred": True}),
            content_type="application/json")
        self.assertIn(resp.status_code, (401, 403))
