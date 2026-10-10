"""Pages with password fields must load the show/hide password toggle."""
from django.test import TestCase


class PasswordToggleTests(TestCase):

    def test_pages_with_password_fields_load_toggle_script(self):
        for url in ("/login/", "/register/"):
            response = self.client.get(url)
            self.assertContains(response, 'type="password"')
            self.assertContains(response, "password_toggle.js")
