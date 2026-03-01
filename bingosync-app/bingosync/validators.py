"""
Input validators for the HP Bingo Platform.

This module provides validators for user inputs to ensure security and data integrity.
All validators follow Django's validator pattern and can be used in forms and models.
"""

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import re


# Maximum lengths for text fields (from models)
MAX_ROOM_NAME_LENGTH = 255
MAX_PLAYER_NAME_LENGTH = 50
MAX_GOAL_LENGTH = 255


def validate_room_name(value):
    """
    Validate room name for security and usability.

    Rules:
    - Must not be empty after stripping whitespace
    - Must not contain only whitespace
    - Must not exceed maximum length
    - Must not contain control characters
    """
    if not value or not value.strip():
        raise ValidationError(
            "Room name cannot be empty or contain only whitespace.")

    # Check for control characters (ASCII 0-31 and 127)
    if re.search(r'[\x00-\x1f\x7f]', value):
        raise ValidationError("Room name cannot contain control characters.")

    # Check length
    if len(value) > MAX_ROOM_NAME_LENGTH:
        raise ValidationError(
            f"Room name cannot exceed {MAX_ROOM_NAME_LENGTH} characters.")


def validate_player_name(value):
    """
    Validate player/nickname for security and usability.

    Rules:
    - Must not be empty after stripping whitespace
    - Must not contain only whitespace
    - Must not exceed maximum length
    - Must not contain control characters
    """
    if not value or not value.strip():
        raise ValidationError(
            "Player name cannot be empty or contain only whitespace.")

    # Check for control characters (ASCII 0-31 and 127)
    if re.search(r'[\x00-\x1f\x7f]', value):
        raise ValidationError("Player name cannot contain control characters.")

    # Check length
    if len(value) > MAX_PLAYER_NAME_LENGTH:
        raise ValidationError(
            f"Player name cannot exceed {MAX_PLAYER_NAME_LENGTH} characters.")


def validate_seed(value):
    """
    Validate seed value for board generation.

    Rules:
    - Must be a non-negative integer
    - Must be within reasonable range (0 to 999999999)
    """
    if value is None or value == "":
        # Empty seed is allowed (will be randomized)
        return

    try:
        seed_int = int(value)
    except (ValueError, TypeError):
        raise ValidationError("Seed must be a valid integer.")

    if seed_int < 0:
        raise ValidationError("Seed must be non-negative.")

    if seed_int > 999999999:
        raise ValidationError("Seed must be less than 1,000,000,000.")


def validate_board_size(value):
    """
    Validate board size.

    Rules:
    - Must be a positive integer
    - Must be between 1 and 10 (reasonable range)
    """
    if value is None or value == "":
        # Empty size is allowed (will use default)
        return

    try:
        size_int = int(value)
    except (ValueError, TypeError):
        raise ValidationError("Board size must be a valid integer.")

    if size_int < 1:
        raise ValidationError("Board size must be at least 1.")

    if size_int > 10:
        raise ValidationError("Board size cannot exceed 10.")


def validate_passphrase(value):
    """
    Validate room passphrase.

    Rules:
    - Must not be empty
    - Must be at least 1 character (no minimum for usability)
    - Must not exceed 255 characters
    """
    if not value:
        raise ValidationError("Password cannot be empty.")

    if len(value) > 255:
        raise ValidationError("Password cannot exceed 255 characters.")


def validate_no_html_tags(value):
    """
    Validate that input doesn't contain HTML tags.

    This is a defense-in-depth measure. Django templates auto-escape by default,
    but we also validate at the form level.

    This checks for actual HTML tags (opening or closing), not just angle brackets.
    """
    # Match actual HTML tags: <tag> or </tag> or <tag attr="value">
    # But not just < or > symbols with spaces around them
    if re.search(r'<\s*[a-zA-Z][^>]*>', value):
        raise ValidationError("Input cannot contain HTML tags.")


def validate_no_script_tags(value):
    """
    Validate that input doesn't contain script tags or javascript: URLs.

    This is a defense-in-depth measure against XSS.
    """
    # Check for script tags (case-insensitive)
    if re.search(
        r'<script[^>]*>.*?</script>',
        value,
            re.IGNORECASE | re.DOTALL):
        raise ValidationError("Input cannot contain script tags.")

    # Check for javascript: URLs
    if re.search(r'javascript:', value, re.IGNORECASE):
        raise ValidationError("Input cannot contain javascript: URLs.")

    # Check for event handlers (onclick, onerror, etc.)
    if re.search(r'\bon\w+\s*=', value, re.IGNORECASE):
        raise ValidationError("Input cannot contain event handlers.")


def sanitize_text_input(value):
    """
    Sanitize text input by removing potentially dangerous characters.

    This function:
    - Strips leading/trailing whitespace
    - Removes control characters
    - Normalizes whitespace

    Returns the sanitized string.
    """
    if not value:
        return value

    # Strip leading/trailing whitespace
    value = value.strip()

    # Remove control characters (except newlines and tabs for multi-line
    # fields)
    value = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]', '', value)

    # Normalize multiple spaces to single space
    value = re.sub(r' +', ' ', value)

    return value


# Regex validator for alphanumeric with spaces and common punctuation
alphanumeric_with_punctuation = RegexValidator(
    regex=r'^[a-zA-Z0-9\s\-_.,!?\'\"()]+$',
    message='Only letters, numbers, spaces, and common punctuation are allowed.',
    code='invalid_characters')
