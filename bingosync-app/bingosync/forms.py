from django import forms
from django.db import transaction
from django.contrib.auth import hashers
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

import json
import logging
import random

from bingosync.generators import InvalidBoardException
from bingosync.models import Room, GameType, LockoutMode, Game, Player, FilteredPattern
from bingosync.models.user import User
from bingosync.goals_converter import download_and_get_converted_goal_list, DEFAULT_DOWNLOAD_URL
from bingosync.widgets import GroupedSelect
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
        validators=[validate_room_name, validate_no_html_tags, validate_no_script_tags]
    )
    passphrase = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(),
        validators=[validate_passphrase]
    )
    nickname = forms.CharField(
        label="Nickname",
        max_length=PLAYER_NAME_MAX_LENGTH,
        validators=[validate_player_name, validate_no_html_tags, validate_no_script_tags]
    )
    # Hidden fields - automatically set to HP CoS (value 50)
    game_type = forms.CharField(widget=forms.HiddenInput(), initial='50', required=False)
    variant_type = forms.CharField(widget=forms.HiddenInput(), initial='50', required=False)
    custom_json = forms.CharField(label="Board", widget=forms.Textarea(attrs={'rows': 6, 'placeholder': CUSTOM_JSON_PLACEHOLDER_TEXT}), required=False)
    lockout_mode = forms.ChoiceField(label="Mode", choices=LockoutMode.choices())
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
    is_spectator = forms.BooleanField(label="Create as Spectator", required=False)
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
            cleaned_data["custom_board"] = generator.validate_custom_json(custom_json, size=cleaned_data.get('size') or 5)
        except InvalidBoardException as e:
            raise forms.ValidationError(e)

        return cleaned_data

    def create_room(self):
        room_name = self.cleaned_data["room_name"]
        passphrase = self.cleaned_data["passphrase"]
        nickname = self.cleaned_data["nickname"]
        game_type = GameType.for_value(int(self.cleaned_data["game_type"]))
        lockout_mode = LockoutMode.for_value(int(self.cleaned_data["lockout_mode"]))
        seed = self.cleaned_data["seed"]
        size = self.cleaned_data["size"]
        custom_board = self.cleaned_data.get("custom_board", [])
        is_spectator = self.cleaned_data["is_spectator"]
        hide_card = self.cleaned_data["hide_card"]
        fog_of_war = self.cleaned_data["fog_of_war"]

        # Note: room_name and nickname are already sanitized and filtered in clean_* methods

        if not seed:
            seed = "" if game_type.uses_seed else "0"

        seed, board_json = game_type.generator_instance().get_card(seed, custom_board, size)

        encrypted_passphrase = hashers.make_password(passphrase)
        with transaction.atomic():
            room = Room(name=room_name, passphrase=encrypted_passphrase, hide_card=hide_card)
            room.save()

            game = Game.from_board(board_json, room=room, game_type_value=game_type.value,
                    lockout_mode_value=lockout_mode.value, seed=seed, fog_of_war=fog_of_war)

            creator = Player(room=room, name=nickname, is_spectator=is_spectator)
            creator.save()

            room.update_active()
        return room

class JoinRoomForm(forms.Form):
    encoded_room_uuid = forms.CharField(label="Room UUID", max_length=128, widget=forms.HiddenInput())
    room_name = make_read_only_char_field(label="Room Name", max_length=ROOM_NAME_MAX_LENGTH)
    creator_name = make_read_only_char_field(label="Creator", max_length=PLAYER_NAME_MAX_LENGTH)
    game_name = make_read_only_char_field(label="Game")
    player_name = forms.CharField(
        label="Nickname",
        max_length=PLAYER_NAME_MAX_LENGTH,
        validators=[validate_player_name, validate_no_html_tags, validate_no_script_tags]
    )
    passphrase = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(render_value=True),
        validators=[validate_passphrase]
    )
    is_spectator = forms.BooleanField(label="Join as Spectator", required=False)

    def __init__(self, *args, **kwargs):
        super(JoinRoomForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_tag = False

        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-md-3'
        self.helper.field_class = 'col-md-9'

    @staticmethod
    def for_room(room):
        initial_values = {
            "encoded_room_uuid": room.encoded_uuid,
            "room_name": room.name,
            "creator_name": room.creator.name,
            "game_name": room.current_game.game_type.long_name,
        }
        return JoinRoomForm(initial=initial_values)

    def get_room(self):
        encoded_room_uuid = self.cleaned_data["encoded_room_uuid"]
        return Room.get_for_encoded_uuid(encoded_room_uuid)

    def clean_player_name(self):
        """Clean and sanitize player name."""
        player_name = self.cleaned_data.get('player_name', '')
        # Sanitize input
        player_name = sanitize_text_input(player_name)
        # Apply profanity filter
        player_name = FilteredPattern.filter_string(player_name)
        return player_name

    def clean(self):
        cleaned_data = super(JoinRoomForm, self).clean()
        encoded_room_uuid = cleaned_data.get("encoded_room_uuid")
        passphrase = cleaned_data.get("passphrase")

        if encoded_room_uuid and passphrase:
            room = Room.get_for_encoded_uuid(encoded_room_uuid)
            if not hashers.check_password(passphrase, room.passphrase):
                raise forms.ValidationError("Incorrect Password")

    def create_player(self):
        room = Room.get_for_encoded_uuid(self.cleaned_data["encoded_room_uuid"])
        nickname = self.cleaned_data["player_name"]
        is_spectator = self.cleaned_data["is_spectator"]

        # Note: nickname is already sanitized and filtered in clean_player_name method

        with transaction.atomic():
            player = Player(room=room, name=nickname, is_spectator=is_spectator)
            player.save()

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
        except Exception as e:
            logger.error("failed to download url: " + str(spreadsheet_url), exc_info=True)
            raise forms.ValidationError("Unable to get goal list")

    def get_goal_list(self):
        return self.json_str


class UserRegistrationForm(forms.Form):
    """Form for user registration with username, email, and password."""
    
    username = forms.CharField(
        label="Username",
        max_length=150,
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
        validators=[validate_no_html_tags, validate_no_script_tags]
    )
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
            raise ValidationError("A user with that email address already exists.")
        
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
        
        # Create user with Django's built-in User model (uses PBKDF2 by default)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        logger.info("New user registered: %s", username)
        return user
