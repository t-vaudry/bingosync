from django import test

import json

from bingosync import models, forms, generators

NO_ACTIVE_ROOMS_TEXT = "Global Stats"
MAKE_ROOM_BUTTON = '<input type="submit" class="form-control" value="Make Room" />'
JOIN_ROOM_BUTTON = '<input type="submit" class="form-control" value="Join Room" />'
BOARD_CONTAINER_HTML = '<div class="board-container">'

TEST_GAME_TYPE = models.GameType.hp_cos

def filter_keys(d, keys):
    return dict((k, v) for k, v in d.items() if k in keys)

def inject_eval_generator_exception(generator, message=""):
    old_eval = generator.eval
    def new_eval(*args, **kwargs):
        generator.eval = old_eval
        raise generators.GeneratorException(message)
    generator.eval = new_eval

class HomeTestCase(test.TestCase):

    def setUp(self):
        self.room_form = forms.RoomForm({
            "room_name": "Test Room",
            "passphrase": "password",
            "nickname": "Bingoer",
            "game_type": str(TEST_GAME_TYPE.value),
            "lockout_mode": str(models.LockoutMode.lockout.value),
        })

    def test_home_empty(self):
        resp = self.client.get("/")
        self.assertContains(resp, NO_ACTIVE_ROOMS_TEXT)
        self.assertContains(resp, MAKE_ROOM_BUTTON, html=True)

    def test_home_create_room(self):
        self.assertTrue(self.room_form.is_valid())
        # test room creation
        create_resp = self.client.post("/", self.room_form.data, follow=True)
        self.assertContains(create_resp, "Test Room")
        self.assertContains(create_resp, BOARD_CONTAINER_HTML)
        self.assertNotContains(create_resp, JOIN_ROOM_BUTTON)

        room_url = create_resp.context["room"].get_absolute_url()

        # test that the creator is redirected properly
        creator_resp = self.client.get(room_url)
        self.assertContains(creator_resp, "Test Room")
        self.assertContains(creator_resp, BOARD_CONTAINER_HTML)
        self.assertNotContains(creator_resp, JOIN_ROOM_BUTTON)

        # test that a new user gets the join screen
        new_resp = test.Client().get(room_url)
        self.assertContains(new_resp, "Test Room")
        self.assertNotContains(new_resp, BOARD_CONTAINER_HTML)
        self.assertContains(new_resp, JOIN_ROOM_BUTTON, html=True)

    def test_home_create_room_timeout(self):
        inject_eval_generator_exception(TEST_GAME_TYPE.generator_instance(), "some error message")

        self.assertTrue(self.room_form.is_valid())
        # create room with expected generation error
        create_resp = self.client.post("/", self.room_form.data, follow=True)
        # assert that the old form values and error message are present
        self.assertContains(create_resp, "Test Room")
        self.assertContains(create_resp, "some error message")
        # assert that we're back on the create room page
        self.assertContains(create_resp, MAKE_ROOM_BUTTON, html=True)
        self.assertNotContains(create_resp, BOARD_CONTAINER_HTML)
        self.assertNotContains(create_resp, JOIN_ROOM_BUTTON)

        self.assertTrue(self.room_form.is_valid())
        # try again and succeed
        create_resp = self.client.post("/", self.room_form.data, follow=True)
        self.assertContains(create_resp, "Test Room")
        self.assertContains(create_resp, BOARD_CONTAINER_HTML)
        self.assertNotContains(create_resp, JOIN_ROOM_BUTTON)

    def test_home_one_room(self):
        # test home page when one room already exists
        if not self.room_form.is_valid():
            self.fail("form error: " + repr(self.room_form.errors))
        room = self.room_form.create_room()
        resp = self.client.get("/")
        # The home page now shows global stats, not a list of rooms
        self.assertContains(resp, "Global Stats")
        self.assertContains(resp, MAKE_ROOM_BUTTON, html=True)


class ApiTestCase(test.TestCase):

    def test_join_room_api(self):
        # create a room to join
        room_resp = self.client.post("/", {
            "room_name": "Test Room",
            "passphrase": "test password",
            "nickname": "Bingoer",
            "game_type": str(models.GameType.hp_cos.value),
            "lockout_mode": str(models.LockoutMode.lockout.value),
        }, follow=True)

        room_encoded_uuid = room_resp.context["room"].encoded_uuid

        # join the room via api, expect to get redirected to the socket key endpoint
        join_room_resp = self.client.post("/api/join-room", json.dumps({
            "room": room_encoded_uuid,
            "nickname": "other user",
            "password": "test password",
        }), content_type="application/json", follow=True)
        self.assertTrue("socket_key" in join_room_resp.json())

        # request a socket key explicitly as well
        socket_key_resp = self.client.get("/api/get-socket-key/" + room_encoded_uuid)
        self.assertTrue("socket_key" in socket_key_resp.json())
        socket_key = socket_key_resp.json()["socket_key"]

        # check that the socket key is valid
        check_socket_key_resp = self.client.get("/api/socket/" + socket_key)
        self.assertEqual(check_socket_key_resp.status_code, 200)

    def test_join_room_api_wrong_password(self):
        # create a room to join
        room_resp = self.client.post("/", {
            "room_name": "Test Room",
            "passphrase": "test password",
            "nickname": "Bingoer",
            "game_type": str(models.GameType.hp_cos.value),
            "lockout_mode": str(models.LockoutMode.lockout.value),
        }, follow=True)

        room_encoded_uuid = room_resp.context["room"].encoded_uuid

        # try to join the room via api, but give the wrong password
        join_room_resp = self.client.post("/api/join-room", json.dumps({
            "room": room_encoded_uuid,
            "nickname": "other user",
            "password": "wrong password",
        }), content_type="application/json", follow=True)
        self.assertContains(join_room_resp, "Incorrect Password", status_code=400)

