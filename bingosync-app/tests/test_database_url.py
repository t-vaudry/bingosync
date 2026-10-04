"""
Tests for building the database URL from separate DB_* settings, which is how
docker-compose.yml connects to either the bundled Postgres or your own.
"""
import dj_database_url
from django.test import SimpleTestCase

from bingosync.settings import _database_url_from_parts


class DatabaseUrlFromPartsTests(SimpleTestCase):

    def test_defaults_for_bundled_database(self):
        url = _database_url_from_parts({
            "DB_HOST": "postgres", "DB_PASSWORD": "secret"})
        self.assertEqual(
            url, "postgresql://bingosync:secret@postgres:5432/bingosync")

    def test_existing_server_settings(self):
        config = dj_database_url.parse(_database_url_from_parts({
            "DB_HOST": "192.168.1.10", "DB_PORT": "5433",
            "DB_NAME": "bingo", "DB_USER": "bingo_user",
            "DB_PASSWORD": "secret"}))
        self.assertEqual(config["HOST"], "192.168.1.10")
        self.assertEqual(config["PORT"], 5433)
        self.assertEqual(config["NAME"], "bingo")
        self.assertEqual(config["USER"], "bingo_user")

    def test_password_with_url_characters_survives(self):
        password = "p@ss:w/rd#?%"
        config = dj_database_url.parse(_database_url_from_parts({
            "DB_HOST": "postgres", "DB_PASSWORD": password}))
        self.assertEqual(config["PASSWORD"], password)
        self.assertEqual(config["HOST"], "postgres")

    def test_blank_values_fall_back_to_defaults(self):
        # docker-compose passes unset variables through as empty strings
        url = _database_url_from_parts({
            "DB_HOST": "postgres", "DB_PORT": "", "DB_NAME": "",
            "DB_USER": "", "DB_PASSWORD": "secret"})
        self.assertEqual(
            url, "postgresql://bingosync:secret@postgres:5432/bingosync")
