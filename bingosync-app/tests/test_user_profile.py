"""
Tests for the public player profile page (/users/<username>).
"""
from django.test import TestCase, Client

from bingosync.models.user import User


class UserProfileTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", email="a@t.com", password="pw12345678")
        self.user.wins = 3
        self.user.losses = 1
        self.user.total_bingos_completed = 5
        self.user.total_squares_marked = 42
        self.user.total_games_played = 4
        self.user.save()
        self.client = Client()

    def test_profile_renders_with_stats(self):
        resp = self.client.get("/users/alice")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn("alice", content)
        self.assertIn("42", content)          # squares marked
        self.assertIn("Win rate", content)
        self.assertIn("75%", content)         # 3 wins of 4 lockout games

    def test_profile_lookup_is_case_insensitive(self):
        self.assertEqual(self.client.get("/users/ALICE").status_code, 200)

    def test_unknown_user_returns_404(self):
        self.assertEqual(self.client.get("/users/nobody").status_code, 404)

    def test_profile_is_public(self):
        # No login; a profile is still viewable.
        self.assertEqual(self.client.get("/users/alice").status_code, 200)
