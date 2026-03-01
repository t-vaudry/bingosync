from django import forms
from django.db import transaction
from django.contrib.auth import hashers
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

import logging

from bingosync.generators import InvalidBoardException
from bingosync.models import Room, GameType, LockoutMode, Game, Player, FilteredPattern
from bingosync.models.user import User
from bingosync.models.enums import Role
from bingosync.goals_converter import download_and_get_converted_goal_list, DEFAULT_DOWNLOAD_URL
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

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Field


logger = logging.getLogger(__name__)


def make_read_only_char_field(*args, **kwargs):
    kwargs["widget"] = forms.TextInput(attrs={"readonly": "readonly"})
    return forms.CharField(*args, **kwargs)


ROOM_NAME_MAX_LENGTH = Room._meta.get_field("name").max_length
PLAYER_NAME_MAX_LENGTH = Player._meta.get_field("name").max_length

CUSTOM_JSON_PLACEHOLDER_TEXT = """Paste the board as a JSON list of goals, e.g:
[ {"name": "Collect 3 Fire Flowers"},
  {"name": "Defeat Phantom Ganon"},
  {"name": "Catch a Pokemon while Surfing"},
  ... ]"""


class RoomForm(forms.Form):
    room_name = forms.CharField(
        label="Room Name",
        max_length=ROOM_NAME_MAX_LENGTH,
        validators=[
            validate_room_name,
            validate_no_html_tags,
            validate_no_script_tags])
    passphrase = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(),
        validators=[validate_passphrase]
    )
    nickname = forms.CharField(
        label="Nickname",
        max_length=PLAYER_NAME_MAX_LENGTH,
        validators=[
            validate_player_name,
            validate_no_html_tags,
            validate_no_script_tags])
    # Hidden fields - automatically set to HP CoS (value 50)
    game_type = forms.CharField(
        widget=forms.HiddenInput(),
        initial='50',
        required=False)
    variant_type = forms.CharField(
        widget=forms.HiddenInput(),
        initial='50',
        required=False)
    custom_json = forms.CharField(
        label="Board",
        widget=forms.Textarea(
            attrs={
                'rows': 6,
                'placeholder': CUSTOM_JSON_PLACEHOLDER_TEXT}),
        required=False)
    lockout_mode = forms.ChoiceField(
        label="Mode", choices=LockoutMode.choices())
    seed = forms.CharField(
        label="Seed",
        widget=forms.NumberInput(attrs={"min": 0}),
        help_text="Leave blank for a random seed",
        required=False,
        validators=[validate_seed]
    )
    size = forms.CharField(
        label="Board Size",
        widget=forms.NumberInput(attrs={"min": 1}),
        help_text="Leave blank for the generator's default size (usually 5)",
        required=False,
        validators=[validate_board_size]
    )
    is_spectator = forms.BooleanField(
        label="Create as Spectator", required=False)
    gamemaster_only = forms.BooleanField(
        label="Gamemaster Only",
        required=False,
        help_text=(
            "If checked, you will be Gamemaster only (cannot mark "
            "squares). If unchecked, you will be Gamemaster + Player "
            "(can mark squares)."
        )
    )
    hide_card = forms.BooleanField(label="Hide Card Initially", required=False)
    fog_of_war = forms.BooleanField(label="Fog of War", required=False)

    def __init__(self, *args, **kwargs):
        super(RoomForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_tag = False

        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3'
        self.helper.field_class = 'col-md-9'
        # custom_json hidden by default
        self.helper['custom_json'].wrap(Field, wrapper_class='hidden')

    def clean_room_name(self):
        """Clean and sanitize room name."""
        room_name = self.cleaned_data.get('room_name', '')
        # Sanitize input
        room_name = sanitize_text_input(room_name)
        # Apply profanity filter
        room_name = FilteredPattern.filter_string(room_name)
        return room_name

    def clean_nickname(self):
        """Clean and sanitize nickname."""
        nickname = self.cleaned_data.get('nickname', '')
        # Sanitize input
        nickname = sanitize_text_input(nickname)
        # Apply profanity filter
        nickname = FilteredPattern.filter_string(nickname)
        return nickname

    def clean_seed(self):
        """Clean and validate seed."""
        seed = self.cleaned_data.get('seed', '')
        if seed:
            # Additional validation is done by the validator
            return str(seed).strip()
        return seed

    def clean_size(self):
        """Clean and validate board size."""
        size = self.cleaned_data.get('size', '')
        if size:
            # Additional validation is done by the validator
            return str(size).strip()
        return size

    def clean(self):
        cleaned_data = super(RoomForm, self).clean()

        # Always use HP Chamber of Secrets (value 50)
        cleaned_data["game_type"] = "50"
        game_type = GameType.for_value(50)
        generator = game_type.generator_instance()

        custom_json = cleaned_data.get("custom_json", "")
        try:
            cleaned_data["custom_board"] = generator.validate_custom_json(
                custom_json, size=cleaned_data.get('size') or 5)
        except InvalidBoardException as e:
            raise forms.ValidationError(e)

        return cleaned_data

    def create_room(self, user=None):
        """
        Create a new room with the specified settings.

        Args:
            user: Optional authenticated User instance

        Returns:
            Room instance

        Raises:
            ValidationError: If authenticated user is already in another room
        """
        room_name = self.cleaned_data["room_name"]
        passphrase = self.cleaned_data["passphrase"]
        nickname = self.cleaned_data["nickname"]
        game_type = GameType.for_value(int(self.cleaned_data["game_type"]))
        lockout_mode = LockoutMode.for_value(
            int(self.cleaned_data["lockout_mode"]))
        seed = self.cleaned_data["seed"]
        size = self.cleaned_data["size"]
        custom_board = self.cleaned_data.get("custom_board", [])
        is_spectator = self.cleaned_data["is_spectator"]
        gamemaster_only = self.cleaned_data.get("gamemaster_only", False)
        hide_card = self.cleaned_data["hide_card"]
        fog_of_war = self.cleaned_data["fog_of_war"]

        # Note: room_name and nickname are already sanitized and filtered in
        # clean_* methods

        # Check if authenticated user is already in a room
        if user and user.is_authenticated:
            if user.current_room:
                raise ValidationError(
                    f"You are already in room '{user.current_room.name}'. "
                    f"Please leave that room before creating another."
                )

        if not seed:
            seed = "" if game_type.uses_seed else "0"

        seed, board_json = game_type.generator_instance().get_card(seed, custom_board, size)

        encrypted_passphrase = hashers.make_password(passphrase)
        with transaction.atomic():
            room = Room(
                name=room_name,
                passphrase=encrypted_passphrase,
                hide_card=hide_card)
            room.save()

            Game.from_board(
                board_json,
                room=room,
                game_type_value=game_type.value,
                lockout_mode_value=lockout_mode.value,
                seed=seed,
                fog_of_war=fog_of_war)

            # Determine role and is_also_player based on form inputs
            if is_spectator:
                # User chose to be a spectator
                role = Role.SPECTATOR
                is_also_player_flag = False
            elif gamemaster_only:
                # User chose Gamemaster-only (cannot mark squares)
                role = Role.GAMEMASTER
                is_also_player_flag = False
            else:
                # Default: Gamemaster + Player (can mark squares)
                role = Role.GAMEMASTER
                is_also_player_flag = True

            creator = Player(
                room=room,
                name=nickname,
                role=role,
                is_also_player=is_also_player_flag
            )
            creator.save()

            # Set current_room for authenticated users
            if user and user.is_authenticated:
                user.current_room = room
                user.save()

            room.update_active()
        return room


class JoinRoomForm(forms.Form):
    encoded_room_uuid = forms.CharField(widget=forms.HiddenInput())
    player_name = forms.CharField(
        label="Nickname",
        max_length=50,
        validators=[
            validate_player_name,
            validate_no_html_tags,
            validate_no_script_tags]
    )
    passphrase = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(),
        validators=[validate_passphrase]
    )
    role = forms.ChoiceField(
        label="Join as",
        choices=[
            (Role.PLAYER, 'Player'),
            (Role.SPECTATOR, 'Spectator'),
            (Role.COUNTER, 'Counter'),
        ],
        initial=Role.PLAYER,
        required=True
    )

    def __init__(self, *args, **kwargs):
        self.room = kwargs.pop('room', None)
        super().__init__(*args, **kwargs)
        if self.room:
            self.fields['encoded_room_uuid'].initial = self.room.encoded_uuid

    @staticmethod
    def for_room(room):
        return JoinRoomForm(room=room)

    def get_room(self):
        if not self.room:
            encoded_uuid = self.cleaned_data.get("encoded_room_uuid")
            if encoded_uuid:
                self.room = Room.get_for_encoded_uuid(encoded_uuid)
        return self.room

    def clean_player_name(self):
        """Sanitize player name by removing HTML tags and normalizing whitespace."""
        import re
        from django.utils.html import strip_tags

        player_name = self.cleaned_data.get('player_name', '')

        # Strip HTML tags
        player_name = strip_tags(player_name)

        # Check if HTML tags were present (after stripping, if different)
        original = self.data.get('player_name', '')
        if strip_tags(original) != original:
            raise ValidationError("Player name cannot contain HTML tags.")

        # Normalize whitespace: strip leading/trailing and collapse multiple spaces
        player_name = re.sub(r'\s+', ' ', player_name.strip())

        return player_name

    def clean(self):
        cleaned_data = super().clean()
        room = self.get_room()
        passphrase = cleaned_data.get("passphrase")
        if room and passphrase and not hashers.check_password(
                passphrase, room.passphrase):
            raise ValidationError("Incorrect Password")
        return cleaned_data

    def create_player(self, user=None):
        """
        Create a player for the room.

        Args:
            user: Optional authenticated User instance

        Returns:
            Player instance

        Raises:
            ValidationError: If authenticated user is already in another room
        """
        room = Room.get_for_encoded_uuid(
            self.cleaned_data["encoded_room_uuid"])
        nickname = self.cleaned_data["player_name"]
        role = self.cleaned_data["role"]

        # Note: nickname is already sanitized and filtered in clean_player_name
        # method

        # Check if authenticated user is already in a room
        if user and user.is_authenticated:
            if user.current_room and user.current_room != room:
                raise ValidationError(
                    f"You are already in room '{user.current_room.name}'. "
                    f"Please leave that room before joining another."
                )

        with transaction.atomic():
            player = Player(room=room, name=nickname, role=role)
            player.save()

            # Set current_room for authenticated users
            if user and user.is_authenticated:
                user.current_room = room
                user.save()

            room.update_active()

            return player


class GoalListConverterForm(forms.Form):
    spreadsheet_url = forms.CharField(label="Spreadsheet URL")

    def __init__(self, *args, **kwargs):
        super(GoalListConverterForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_tag = False

        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3'
        self.helper.field_class = 'col-md-9'

    @staticmethod
    def get():
        initial_values = {
            "spreadsheet_url": DEFAULT_DOWNLOAD_URL,
        }
        return GoalListConverterForm(initial=initial_values)

    def clean(self):
        cleaned_data = super(GoalListConverterForm, self).clean()
        spreadsheet_url = cleaned_data["spreadsheet_url"]

        try:
            json_str = download_and_get_converted_goal_list(spreadsheet_url)
            # make the json actually javascript
            json_str = "var bingoList = " + json_str
            self.json_str = json_str
        except Exception:
            logger.error(
                "failed to download url: "
                + str(spreadsheet_url),
                exc_info=True)
            raise forms.ValidationError("Unable to get goal list")

    def get_goal_list(self):
        return self.json_str


class UserRegistrationForm(forms.Form):
    """Form for user registration with username, email, and password."""

    username = forms.CharField(
        label="Username",
        max_length=150,
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
        validators=[
            validate_no_html_tags,
            validate_no_script_tags])
    email = forms.EmailField(
        label="Email",
        max_length=254,
        help_text="Required. Enter a valid email address."
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(),
        help_text="Your password must contain at least 8 characters."
    )
    password_confirm = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(),
        help_text="Enter the same password as before, for verification."
    )

    def __init__(self, *args, **kwargs):
        super(UserRegistrationForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_tag = False
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3'
        self.helper.field_class = 'col-md-9'

    def clean_username(self):
        """Validate and sanitize username."""
        username = self.cleaned_data.get('username', '')

        # Sanitize input
        username = sanitize_text_input(username)

        # Apply profanity filter
        username = FilteredPattern.filter_string(username)

        # Check if username already exists
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with that username already exists.")

        return username

    def clean_email(self):
        """Validate email address."""
        email = self.cleaned_data.get('email', '')

        # Check if email is already registered
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(
                "A user with that email address already exists.")

        return email.lower()

    def clean_password(self):
        """Validate password strength."""
        password = self.cleaned_data.get('password', '')

        # Use Django's built-in password validators
        try:
            validate_password(password)
        except ValidationError as e:
            # Re-raise with the error messages
            raise ValidationError(list(e.messages))

        return password

    def clean(self):
        """Validate that passwords match."""
        cleaned_data = super(UserRegistrationForm, self).clean()
        password = cleaned_data.get('password')
        password_confirm = cleaned_data.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise ValidationError("The two password fields didn't match.")

        return cleaned_data

    def create_user(self):
        """Create a new user with hashed password."""
        username = self.cleaned_data['username']
        email = self.cleaned_data['email']
        password = self.cleaned_data['password']

        # Create user with Django's built-in User model (uses PBKDF2 by
        # default)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        logger.info("New user registered: %s", username)
        return user


class UserLoginForm(forms.Form):
    """Form for user login with username and password."""

    username = forms.CharField(
        label="Username",
        max_length=150,
        widget=forms.TextInput(attrs={'autofocus': True})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput()
    )
    remember_me = forms.BooleanField(
        label="Remember me",
        required=False,
        help_text="Keep me logged in for 2 weeks"
    )

    def __init__(self, *args, **kwargs):
        super(UserLoginForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_tag = False
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3'
        self.helper.field_class = 'col-md-9'
