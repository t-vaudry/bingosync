"""
Tests for input validators.

This module tests all validators in bingosync.validators to ensure
proper input validation and sanitization.
"""

from django.test import TestCase
from django.core.exceptions import ValidationError

from bingosync.validators import (
    validate_room_name,
    validate_player_name,
    validate_seed,
    validate_board_size,
    validate_passphrase,
    validate_no_html_tags,
    validate_no_script_tags,
    sanitize_text_input,
)


class ValidateRoomNameTestCase(TestCase):
    """Test room name validation."""

    def test_valid_room_name(self):
        """Valid room names should pass validation."""
        valid_names = [
            "My Room",
            "HP CoS Bingo",
            "Room 123",
            "Test-Room_2024",
            "A" * 255,  # Max length
        ]
        for name in valid_names:
            with self.subTest(name=name):
                validate_room_name(name)  # Should not raise

    def test_empty_room_name(self):
        """Empty room names should fail validation."""
        with self.assertRaises(ValidationError):
            validate_room_name("")

    def test_whitespace_only_room_name(self):
        """Whitespace-only room names should fail validation."""
        with self.assertRaises(ValidationError):
            validate_room_name("   ")

    def test_room_name_with_control_characters(self):
        """Room names with control characters should fail validation."""
        with self.assertRaises(ValidationError):
            validate_room_name("Room\x00Name")
        with self.assertRaises(ValidationError):
            validate_room_name("Room\x1fName")

    def test_room_name_too_long(self):
        """Room names exceeding max length should fail validation."""
        with self.assertRaises(ValidationError):
            validate_room_name("A" * 256)


class ValidatePlayerNameTestCase(TestCase):
    """Test player name validation."""

    def test_valid_player_name(self):
        """Valid player names should pass validation."""
        valid_names = [
            "Player1",
            "John Doe",
            "Test_Player",
            "A" * 50,  # Max length
        ]
        for name in valid_names:
            with self.subTest(name=name):
                validate_player_name(name)  # Should not raise

    def test_empty_player_name(self):
        """Empty player names should fail validation."""
        with self.assertRaises(ValidationError):
            validate_player_name("")

    def test_whitespace_only_player_name(self):
        """Whitespace-only player names should fail validation."""
        with self.assertRaises(ValidationError):
            validate_player_name("   ")

    def test_player_name_with_control_characters(self):
        """Player names with control characters should fail validation."""
        with self.assertRaises(ValidationError):
            validate_player_name("Player\x00Name")

    def test_player_name_too_long(self):
        """Player names exceeding max length should fail validation."""
        with self.assertRaises(ValidationError):
            validate_player_name("A" * 51)


class ValidateSeedTestCase(TestCase):
    """Test seed validation."""

    def test_valid_seed(self):
        """Valid seeds should pass validation."""
        valid_seeds = [0, 1, 12345, 999999999, "12345"]
        for seed in valid_seeds:
            with self.subTest(seed=seed):
                validate_seed(seed)  # Should not raise

    def test_empty_seed(self):
        """Empty seed should pass validation (will be randomized)."""
        validate_seed("")
        validate_seed(None)

    def test_negative_seed(self):
        """Negative seeds should fail validation."""
        with self.assertRaises(ValidationError):
            validate_seed(-1)

    def test_seed_too_large(self):
        """Seeds exceeding max value should fail validation."""
        with self.assertRaises(ValidationError):
            validate_seed(1000000000)

    def test_non_numeric_seed(self):
        """Non-numeric seeds should fail validation."""
        with self.assertRaises(ValidationError):
            validate_seed("abc")


class ValidateBoardSizeTestCase(TestCase):
    """Test board size validation."""

    def test_valid_board_size(self):
        """Valid board sizes should pass validation."""
        valid_sizes = [1, 5, 10, "5"]
        for size in valid_sizes:
            with self.subTest(size=size):
                validate_board_size(size)  # Should not raise

    def test_empty_board_size(self):
        """Empty board size should pass validation (will use default)."""
        validate_board_size("")
        validate_board_size(None)

    def test_zero_board_size(self):
        """Zero board size should fail validation."""
        with self.assertRaises(ValidationError):
            validate_board_size(0)

    def test_negative_board_size(self):
        """Negative board sizes should fail validation."""
        with self.assertRaises(ValidationError):
            validate_board_size(-1)

    def test_board_size_too_large(self):
        """Board sizes exceeding max value should fail validation."""
        with self.assertRaises(ValidationError):
            validate_board_size(11)

    def test_non_numeric_board_size(self):
        """Non-numeric board sizes should fail validation."""
        with self.assertRaises(ValidationError):
            validate_board_size("abc")


class ValidatePassphraseTestCase(TestCase):
    """Test passphrase validation."""

    def test_valid_passphrase(self):
        """Valid passphrases should pass validation."""
        valid_passphrases = [
            "password",
            "p",
            "A" * 255,  # Max length
            "P@ssw0rd!",
        ]
        for passphrase in valid_passphrases:
            with self.subTest(passphrase=passphrase):
                validate_passphrase(passphrase)  # Should not raise

    def test_empty_passphrase(self):
        """Empty passphrases should fail validation."""
        with self.assertRaises(ValidationError):
            validate_passphrase("")

    def test_passphrase_too_long(self):
        """Passphrases exceeding max length should fail validation."""
        with self.assertRaises(ValidationError):
            validate_passphrase("A" * 256)


class ValidateNoHtmlTagsTestCase(TestCase):
    """Test HTML tag validation."""

    def test_valid_input_without_html(self):
        """Input without HTML tags should pass validation."""
        valid_inputs = [
            "Plain text",
            "Text with > and < symbols",
            "5 < 10 and 10 > 5",
        ]
        for input_text in valid_inputs:
            with self.subTest(input_text=input_text):
                validate_no_html_tags(input_text)  # Should not raise

    def test_input_with_html_tags(self):
        """Input with HTML tags should fail validation."""
        invalid_inputs = [
            "<div>text</div>",
            "<script>alert('xss')</script>",
            "Text with <b>bold</b> tags",
            "<img src='x'>",
        ]
        for input_text in invalid_inputs:
            with self.subTest(input_text=input_text):
                with self.assertRaises(ValidationError):
                    validate_no_html_tags(input_text)


class ValidateNoScriptTagsTestCase(TestCase):
    """Test script tag validation."""

    def test_valid_input_without_scripts(self):
        """Input without script tags should pass validation."""
        validate_no_script_tags("Plain text")

    def test_input_with_script_tags(self):
        """Input with script tags should fail validation."""
        invalid_inputs = [
            "<script>alert('xss')</script>",
            "<SCRIPT>alert('xss')</SCRIPT>",
            "javascript:alert('xss')",
            "onclick=alert('xss')",
            "onerror=alert('xss')",
        ]
        for input_text in invalid_inputs:
            with self.subTest(input_text=input_text):
                with self.assertRaises(ValidationError):
                    validate_no_script_tags(input_text)


class SanitizeTextInputTestCase(TestCase):
    """Test text input sanitization."""

    def test_sanitize_removes_leading_trailing_whitespace(self):
        """Sanitization should remove leading/trailing whitespace."""
        self.assertEqual(sanitize_text_input("  text  "), "text")

    def test_sanitize_removes_control_characters(self):
        """Sanitization should remove control characters."""
        self.assertEqual(
            sanitize_text_input("text\x00with\x1fcontrol"),
            "textwithcontrol")

    def test_sanitize_normalizes_whitespace(self):
        """Sanitization should normalize multiple spaces to single space."""
        self.assertEqual(
            sanitize_text_input("text  with   spaces"),
            "text with spaces")

    def test_sanitize_empty_input(self):
        """Sanitization should handle empty input."""
        self.assertEqual(sanitize_text_input(""), "")
        self.assertEqual(sanitize_text_input(None), None)

    def test_sanitize_preserves_valid_text(self):
        """Sanitization should preserve valid text."""
        valid_text = "Valid text with punctuation!"
        self.assertEqual(sanitize_text_input(valid_text), valid_text)
