from django.http import (
    HttpResponse, HttpResponseBadRequest, HttpResponseForbidden,
    JsonResponse, Http404
)
from django.shortcuts import render, redirect
from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.db.models import F
from django.template import loader
from django.views.decorators.clickjacking import xframe_options_exempt
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout

import json
import requests
import logging
import urllib.parse

from bingosync.settings import SOCKETS_URL, SOCKETS_PUBLISH_URL
from bingosync.generators import InvalidBoardException, GeneratorException
from bingosync.forms import (
    RoomForm, JoinRoomForm, GoalListConverterForm,
    UserRegistrationForm, UserLoginForm
)
from bingosync.models.colors import Color
from bingosync.models.game_type import GameType, ALL_VARIANTS
from bingosync.models.events import (
    Event, ChatEvent, GoalEvent, RevealedEvent, ConnectionEvent,
    NewCardEvent, RoleChangeEvent, CounterAssignmentEvent, ClaimReviewEvent
)
from bingosync.models.enums import Role
from bingosync.models.rooms import (
    ANON_PLAYER, Room, Game, LockoutMode, Player, Square, CompletedLine
)
from bingosync.models.user import User
from bingosync.publish import (
    publish_goal_event, publish_chat_event, publish_color_event,
    publish_revealed_event
)
from bingosync.publish import (
    publish_connection_event, publish_new_card_event,
    publish_role_change_event, publish_counter_assignment_event
)
from bingosync.util import generate_encoded_uuid
from bingosync.decorators import (
    ratelimit_login,
    ratelimit_registration,
    ratelimit_authenticated_action,
    handle_ratelimit,
    require_internal_api_secret
)
from bingosync.permissions import check_permission, can_generate_board

from crispy_forms.layout import Layout, Field

logger = logging.getLogger(__name__)


def redirect_params(url, params=None, **kwargs):
    response = redirect(url, **kwargs)
    if params:
        query_string = urllib.parse.urlencode(params)
        response['Location'] += '?' + query_string
    return response


def landing(request):
    """Main landing page - offers login or join as spectator."""
    stats = {
        "rooms": Room.objects.count(),
        "games": Game.objects.count(),
        "ticks": GoalEvent.objects.filter(remove_color=False).count(),
        "unticks": GoalEvent.objects.filter(remove_color=True).count(),
    }
    
    params = {
        "stats": stats,
    }
    return render(request, "bingosync/landing.html", params)


def join_by_code(request):
    """Redirect to join room page (for direct URL access only)."""
    room_code = request.GET.get('room_code', '').strip().upper()
    
    if not room_code:
        return redirect('landing')
    
    try:
        room = Room.get_for_room_code(room_code)
        # Redirect to join room page
        return redirect('room_view', encoded_room_uuid=room.encoded_uuid)
    except Room.DoesNotExist:
        # Room not found - redirect back to landing with error
        return redirect_params('landing', params={'error': 'invalid_code'})


@handle_ratelimit
@ratelimit_login
def join_as_spectator(request):
    """Join a room as spectator directly from landing page."""
    if request.method != 'POST':
        return redirect('landing')
    
    room_code = request.POST.get('room_code', '').strip().upper()
    password = request.POST.get('password', '')
    display_name = request.POST.get('display_name', '').strip()
    
    if not room_code or not display_name:
        return redirect_params('landing', params={'error': 'missing_fields'})
    
    try:
        room = Room.get_for_room_code(room_code)
    except Room.DoesNotExist:
        return redirect_params('landing', params={'error': 'invalid_code'})
    
    # Create join form with spectator data
    form_data = {
        'encoded_room_uuid': room.encoded_uuid,
        'player_name': display_name,
        'passphrase': password,
        'role': Role.SPECTATOR,
    }
    
    join_form = JoinRoomForm(data=form_data, room=room, user=None)
    
    if join_form.is_valid():
        try:
            player = join_form.create_player(user=None)
            _save_session_player(request.session, player)
            return redirect('room_view', encoded_room_uuid=room.encoded_uuid)
        except ValidationError as e:
            return redirect_params('landing', params={'error': str(e)})
    else:
        # Form validation failed (likely wrong password)
        error_msg = 'Invalid password or room details'
        if 'passphrase' in join_form.errors:
            error_msg = 'Incorrect password'
        return redirect_params('landing', params={'error': error_msg})


@handle_ratelimit
@ratelimit_login
def join_room_by_code(request):
    """Join a room directly with code, password, and role (for authenticated users)."""
    if request.method != 'POST':
        return redirect('rooms')
    
    if not request.user.is_authenticated:
        return redirect('login')
    
    room_code = request.POST.get('room_code', '').strip().upper()
    password = request.POST.get('password', '')
    role = request.POST.get('role', 'player')
    
    if not room_code:
        return redirect_params('rooms', params={'error': 'missing_code'})
    
    try:
        room = Room.get_for_room_code(room_code)
    except Room.DoesNotExist:
        return redirect_params('rooms', params={'error': 'invalid_code'})
    
    # Create join form with the data
    form_data = {
        'encoded_room_uuid': room.encoded_uuid,
        'player_name': request.user.username,
        'passphrase': password,
        'role': role,
    }
    
    join_form = JoinRoomForm(data=form_data, room=room, user=request.user)
    
    if join_form.is_valid():
        try:
            player = join_form.create_player(user=request.user)
            _save_session_player(request.session, player)
            return redirect('room_view', encoded_room_uuid=room.encoded_uuid)
        except ValidationError as e:
            return redirect_params('rooms', params={'error': str(e)})
    else:
        # Form validation failed (likely wrong password)
        error_msg = 'Invalid password or room details'
        if 'passphrase' in join_form.errors:
            error_msg = 'Incorrect password'
        return redirect_params('rooms', params={'error': error_msg})


@handle_ratelimit
@ratelimit_registration
def rooms(request):
    """Dashboard for authenticated users - room creation and management."""
    # Require authentication
    if not request.user.is_authenticated:
        return redirect('login')
    
    if request.method == "POST":
        form = RoomForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                # Pass the authenticated user to create_room
                room = form.create_room(user=request.user)
                creator = room.creator
                _save_session_player(request.session, creator)
                # Show room code in success message
                return redirect_params(
                    "room_view", encoded_room_uuid=room.encoded_uuid, params={
                        'password': form.cleaned_data['passphrase'],
                        'created': 'true'
                    })
            except ValidationError as e:
                # Handle one-room-per-user validation error
                form.add_error(None, str(e))
            except GeneratorException as e:
                form.add_error(None, str(e))
        else:
            logger.warning(
                "RoomForm errors: %r, custom_json was: %r", form.errors, form.data.get(
                    "custom_json", "")[
                    :2000])
    else:
        form = RoomForm(user=request.user)

    stats = {
        "rooms": Room.objects.count(),
        "games": Game.objects.count(),
        "ticks": GoalEvent.objects.filter(remove_color=False).count(),
        "unticks": GoalEvent.objects.filter(remove_color=True).count(),
    }

    params = {
        "form": form,
        "stats": stats,
        "variants": ALL_VARIANTS,
    }
    return render(request, "bingosync/index.html", params)


@handle_ratelimit
@ratelimit_registration
def register(request):
    """User registration view."""
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.create_user()
                logger.info("User registered successfully: %s", user.username)
                # Redirect to login page after successful registration
                return redirect_params("login", params={'registered': 'true'})
            except Exception as e:
                logger.error("Error creating user: %s", str(e), exc_info=True)
                form.add_error(
                    None, "An error occurred during registration. Please try again.")
    else:
        form = UserRegistrationForm()

    params = {
        "form": form,
    }
    return render(request, "bingosync/register.html", params)


@handle_ratelimit
@ratelimit_login
def login(request):
    """User login view."""
    if request.method == "POST":
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data['remember_me']

            # Authenticate user
            user = authenticate(request, username=username, password=password)

            if user is not None:
                # Login successful
                auth_login(request, user)

                # Set session expiry AFTER logging in (auth_login resets it to
                # default)
                if remember_me:
                    # Remember for 2 weeks
                    request.session.set_expiry(1209600)  # 2 weeks in seconds
                else:
                    # Session expires when browser closes
                    request.session.set_expiry(0)

                # Explicitly save the session to ensure expiry is persisted
                request.session.save()

                # Log successful login
                logger.info(
                    "User logged in successfully: %s from IP: %s",
                    username,
                    request.META.get(
                        'REMOTE_ADDR',
                        'unknown'))

                # Check if there's a next parameter
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                
                # Redirect to dashboard after login
                return redirect("rooms")
            else:
                # Login failed - create a new form with the error
                logger.warning(
                    "Failed login attempt for username: %s from IP: %s",
                    username,
                    request.META.get(
                        'REMOTE_ADDR',
                        'unknown'))
                # Re-create form with original data and add error
                form = UserLoginForm(request.POST)
                form.is_valid()  # Trigger validation to populate cleaned_data
                form.add_error(None, "Invalid username or password.")
    else:
        form = UserLoginForm()

    # Check if user was just registered
    registered = request.GET.get('registered') == 'true'

    params = {
        "form": form,
        "registered": registered,
    }
    return render(request, "bingosync/login.html", params)


def logout(request):
    """User logout view."""
    if request.user.is_authenticated:
        username = request.user.username
        auth_logout(request)
        logger.info("User logged out: %s", username)

    # Redirect to landing page after logout
    return redirect("landing")


@handle_ratelimit
@ratelimit_login
def room_view(request, encoded_room_uuid):
    room = Room.get_for_encoded_uuid_or_404(encoded_room_uuid)
    try:
        if request.method == "POST":
            join_form = JoinRoomForm(request.POST)
            if join_form.is_valid():
                try:
                    # Pass the authenticated user to create_player
                    user = request.user if request.user.is_authenticated else None
                    player = join_form.create_player(user=user)
                    _save_session_player(request.session, player)
                    return redirect_params(
                        "room_view", encoded_room_uuid=encoded_room_uuid, params={
                            'password': join_form.cleaned_data['passphrase']})
                except ValidationError as e:
                    # Handle one-room-per-user validation error
                    join_form.add_error(None, str(e))
                    room = Room.get_for_encoded_uuid_or_404(encoded_room_uuid)
                    return _join_room(request, join_form, room)
            else:
                room = Room.get_for_encoded_uuid_or_404(encoded_room_uuid)
                return _join_room(request, join_form, room)
        else:
            initial_values = {
                "game_type": room.current_game.game_type.group.value,
                "variant_type": room.current_game.game_type.value,
                "lockout_mode": room.current_game.lockout_mode.value,
                "fog_of_war": room.current_game.fog_of_war,
                "hide_card": room.hide_card,
            }
            new_card_form = RoomForm(initial=initial_values)
            new_card_form.helper.layout = Layout(
                "game_type",
                "variant_type",
                "custom_json",
                "lockout_mode",
                "seed",
                "hide_card",
                "fog_of_war",
            )
            new_card_form.helper['variant_type'].wrap(
                Field, wrapper_class='hidden')
            new_card_form.helper['custom_json'].wrap(
                Field, wrapper_class='hidden')
            player = _get_session_player(request.session, room)
            
            # Prevent spectators from accessing inactive rooms
            if player.is_spectator and not room.active:
                # Clear their session and redirect to landing
                _clear_session_player(request.session, room)
                return redirect_params('landing', params={'error': 'room_inactive'})
            
            params = {
                "room": room,
                "game": room.current_game,
                "player": player,
                "sockets_url": SOCKETS_URL,
                "new_card_form": new_card_form,
                "temporary_socket_key": _create_temporary_socket_key(player)
            }
            return render(request, "bingosync/bingosync.html", params)
    except NotAuthenticatedError:
        join_form = JoinRoomForm.for_room(room, user=request.user)
        if 'password' in request.GET:
            join_form.initial['passphrase'] = request.GET['password']
        return _join_room(request, join_form, room)


@xframe_options_exempt
def room_stream(request, encoded_room_uuid):
    room = Room.get_for_encoded_uuid_or_404(encoded_room_uuid)
    params = {
        "room": room,
        "game": room.current_game,
        "sockets_url": SOCKETS_URL,
        "temporary_socket_key": _create_anon_socket_key(room)
    }
    return render(request, "bingosync/stream.html", params)


def _join_room(request, join_form, room):
    params = {
        "form": join_form,
        "room": room,
        "encoded_room_uuid": room.encoded_uuid,
    }
    return render(request, "bingosync/join_room.html", params)


def room_board(request, encoded_room_uuid):
    room = Room.get_for_encoded_uuid_or_404(encoded_room_uuid)
    board = room.current_game.board
    return JsonResponse(board, safe=False)


def room_scores(request, encoded_room_uuid):
    room = Room.get_for_encoded_uuid_or_404(encoded_room_uuid)
    colors = [
        item.name for sublist in room.current_game.squares for item in sublist.color.colors]
    colors = [color for color in colors if color != "blank"]
    colorsDict = {}
    for color in colors:
        if color not in colorsDict:
            colorsDict[color] = 0
        colorsDict[color] += 1
    return JsonResponse(colorsDict, safe=False)


def room_scores2(request, encoded_room_uuid):
    # TODO: Unify this with
    colorNames = [
        "orange",
        "red",
        "blue",
        "green",
        "purple",
        "navy",
        "teal",
        "forest",
        "pink",
        "yellow",
    ]
    lines = [
        [1, 2, 3, 4, 5],  # r1
        [6, 7, 8, 9, 10],  # r2
        [11, 12, 13, 14, 15],  # r3
        [16, 17, 18, 19, 20],  # r4
        [21, 22, 23, 24, 25],  # r5
        [1, 6, 11, 16, 21],  # c1
        [2, 7, 12, 17, 22],  # c2
        [3, 8, 13, 18, 23],  # c3
        [4, 9, 14, 19, 24],  # c4
        [5, 10, 15, 20, 25],  # c5
        [1, 7, 13, 19, 25],  # rtlbr
        [5, 9, 13, 17, 21],  # rtlbr
    ]

    room = Room.get_for_encoded_uuid_or_404(encoded_room_uuid)
    squareColors = [
        (sublist.slot, item.name)
        for sublist in room.current_game.squares
        for item in sublist.color.colors
        if item.name != "blank"
    ]
    colorSquares = {}
    for color in colorNames:
        colorSquares[color] = []
    for (slot, color) in squareColors:
        print(slot, color)
        colorSquares[color].append(slot)

    res = {}
    for color in colorNames:
        squares = colorSquares[color]
        count = len(squares)
        linesCount = sum((all(slot in squares for slot in line))
                         for line in lines)
        res[color] = {"score": count, "lines": linesCount}

    return JsonResponse(res, safe=False)


# AJAX view to render the room settings panel
def room_settings(request, encoded_room_uuid):
    from bingosync.cache import get_room_settings
    
    room = Room.get_for_encoded_uuid(encoded_room_uuid)
    panel = loader.get_template("bingosync/room_settings_panel.html").render(
        {"game": room.current_game, "room": room}, request)
    
    # Use cached room settings
    settings = get_room_settings(room)
    
    return JsonResponse({"panel": panel, "settings": settings})


@handle_ratelimit
@ratelimit_authenticated_action
def new_card(request):
    if request.method != 'PUT':
        return HttpResponseBadRequest("Method not allowed")

    if not request.body:
        return HttpResponseBadRequest("Empty request body")

    data = json.loads(request.body.decode("utf8"))

    room = Room.get_for_encoded_uuid(data["room"])
    player = _get_session_player(request.session, room)

    # Board generation is allowed for the Gamemaster, or any Player when the
    # room has no Gamemaster.
    if not can_generate_board(player):
        return HttpResponseForbidden(
            "You do not have permission to generate a new board.")

    lockout_mode = LockoutMode.for_value(int(data["lockout_mode"]))
    try:
        fog_of_war = True if data["fog_of_war"] == "on" else False
    except BaseException:
        fog_of_war = False
    hide_card = data["hide_card"]
    seed = data["seed"]
    custom_json = data.get("custom_json", "")

    # create new game
    game_type = GameType.for_value(int(data["game_type"]))
    try:
        # variant_type is not sent if the game only has 1 variant, so use it if
        # it's present but fall back to the regular game_type otherwise
        if "variant_type" in data:
            game_type = GameType.for_value(int(data["variant_type"]))
    except ValueError:
        pass

    generator = game_type.generator_instance()

    try:
        # Always use 5x5 board
        custom_board = generator.validate_custom_json(custom_json, size=5)
    except InvalidBoardException as e:
        return HttpResponseBadRequest("Invalid board: " + str(e))

    if not seed:
        seed = "" if game_type.uses_seed else "0"

    try:
        # Always use 5x5 board
        # Use caching for board generation by seed
        from bingosync.cache import get_board_by_seed
        
        # Only cache if we have a valid seed (not empty/random)
        if seed and seed != "":
            def generate_board(s):
                return game_type.generator_instance().get_card(s, custom_board, 5)
            
            seed, board_json = get_board_by_seed(seed, generate_board)
        else:
            # Don't cache random boards (empty seed)
            seed, board_json = game_type.generator_instance().get_card(seed, custom_board, 5)
    except GeneratorException as e:
        return HttpResponseBadRequest(str(e))

    with transaction.atomic():
        Game.from_board(
            board_json,
            room=room,
            game_type_value=game_type.value,
            lockout_mode_value=lockout_mode.value,
            seed=seed,
            fog_of_war=fog_of_war)

        if hide_card != room.hide_card:
            room.hide_card = hide_card
        room.update_active()  # This saves the room

        # The game just replaced counts as a completed game for its players.
        _record_game_played(room)

        new_card_event = NewCardEvent(
            player=player,
            player_color_value=player.color.value,
            game_type_value=game_type.value,
            seed=seed,
            hide_card=hide_card,
            fog_of_war=fog_of_war)
        new_card_event.save()
    publish_new_card_event(new_card_event)

    return HttpResponse("Recieved data: " + str(data))


def history(request):
    hide_solo = request.GET.get('hide_solo')

    if hide_solo:
        base_rooms = Room.get_with_multiple_players()
    else:
        base_rooms = Room.objects.all()

    room_list = base_rooms.order_by("-created_date")
    paginator = Paginator(room_list, 10)  # Show 25 contacts per page

    page = request.GET.get('page')
    try:
        rooms = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        rooms = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        rooms = paginator.page(paginator.num_pages)

    params = {
        'hide_solo': hide_solo,
        'rooms': rooms,
    }
    return render(request, "bingosync/history.html", params)


def about(request):
    return render(request, "bingosync/about.html")


def room_feed(request, encoded_room_uuid):
    room = Room.get_for_encoded_uuid_or_404(encoded_room_uuid)
    # lookup the player to force authentication
    _get_session_player(request.session, room)
    events_to_return = []
    all_included = True

    if request.GET.get('full') == 'true':
        events_to_return = Event.get_all_for_room(room)
    else:
        recent_events = Event.get_all_recent_for_room(room)
        events_to_return = recent_events["events"]
        all_included = recent_events["all_included"]

    all_jsons = [event.to_json() for event in events_to_return]
    return JsonResponse(
        {'events': all_jsons, 'allIncluded': all_included}, safe=False)


def room_disconnect(request, encoded_room_uuid):
    room = Room.get_for_encoded_uuid_or_404(encoded_room_uuid)

    # Clear current_room for authenticated users
    if request.user.is_authenticated and request.user.current_room == room:
        request.user.current_room = None
        request.user.save()

    _clear_session_player(request.session, room)
    
    # Redirect authenticated users to dashboard, anonymous to landing
    if request.user.is_authenticated:
        return redirect("rooms")
    else:
        return redirect("landing")


@handle_ratelimit
@ratelimit_authenticated_action
def goal_selected(request):
    data = parse_body_json_or_400(
        request, required_keys=[
            "room", "slot", "color", "remove_color"])

    room = Room.get_for_encoded_uuid_or_404(data["room"])
    player = _get_session_player(request.session, room)

    # Check permission to mark squares
    if not check_permission(player, 'mark_square'):
        return HttpResponseForbidden(
            "You do not have permission to mark squares.")

    game = room.current_game
    slot = int(data["slot"])
    color = Color.for_name(data["color"])
    remove_color = data["remove_color"]

    # Check if player has an assigned counter
    counter = player.counters.first() if not remove_color else None
    
    # Determine claim status based on counter assignment
    if counter and not remove_color:
        # Counter exists - square needs counter decision
        # Counter will be notified and must choose: under_review, confirm, or reject
        claim_status = 'pending_decision'
    else:
        # No counter or removing color - bypass claim review
        claim_status = 'confirmed'

    goal_event = game.update_goal(player, slot, color, remove_color, claim_status=claim_status)
    if not goal_event:
        return HttpResponseBadRequest("Blocked by Lockout")
    
    publish_goal_event(goal_event)

    # A confirmed mark may complete a lockout win and/or one or more bingos
    # (marks awaiting counter review are not yet confirmed, so they count for
    # neither until reviewed).
    if not remove_color and claim_status == 'confirmed':
        _record_square_marked(player)
        check_and_record_lockout_win(game, player)
        check_and_record_bingos(game, player)

    return HttpResponse("Recieved data: " + str(data))


@handle_ratelimit
@ratelimit_authenticated_action
def chat_message(request):
    data = parse_body_json_or_400(request, required_keys=["room", "text"])

    room = Room.get_for_encoded_uuid_or_404(data["room"])
    player = _get_session_player(request.session, room)
    text = data["text"]

    chat_event = ChatEvent(
        player=player,
        player_color_value=player.color.value,
        body=text)
    chat_event.save()
    publish_chat_event(chat_event)
    return HttpResponse("Recieved data: " + str(data))


@handle_ratelimit
@ratelimit_authenticated_action
def select_color(request):
    data = parse_body_json_or_400(request, required_keys=["room", "color"])

    room = Room.get_for_encoded_uuid_or_404(data["room"])
    player = _get_session_player(request.session, room)
    color = Color.for_name(data["color"])

    color_event = player.update_color(color)
    publish_color_event(color_event)
    return HttpResponse("Received data: " + str(data))


@handle_ratelimit
@ratelimit_authenticated_action
def board_revealed(request):
    data = parse_body_json_or_400(request, required_keys=["room"])

    room = Room.get_for_encoded_uuid_or_404(data["room"])
    player = _get_session_player(request.session, room)

    # Check permission to reveal fog of war
    if not check_permission(player, 'reveal_fog'):
        return HttpResponseForbidden(
            "You do not have permission to reveal the board.")

    revealed_event = RevealedEvent(
        player=player,
        player_color_value=player.color.value)
    revealed_event.save()
    publish_revealed_event(revealed_event)
    return HttpResponse("Received data: " + str(data))


def create_system_chat_message(player, room, message_text, is_counter_message=False):
    """
    Create and broadcast a system chat message.
    
    Args:
        player: The player object to associate with the message (for event tracking)
        room: The room where the message should appear
        message_text: The text content of the system message
        is_counter_message: Whether this is a counter-related message (for chat filtering)
    """
    chat_event = ChatEvent(
        player=player,
        player_color_value=player.color.value,
        body=message_text,
        is_system_message=True
    )
    chat_event.save()
    # Add counter flag to the published JSON (not stored in DB)
    data = chat_event.to_json()
    if is_counter_message:
        data["is_counter_message"] = True
    data["room"] = room.encoded_uuid
    from bingosync.publish import _publish_json
    _publish_json(data, room)


def check_and_record_lockout_win(game, player):
    """Record a lockout win if `player` has just reached the winning threshold.

    In lockout a square belongs to exactly one player, so the win condition is
    simply being first to a majority of *confirmed* squares (13 on a 5x5).
    Safe to call after any square becomes confirmed: it no-ops outside lockout,
    once a game already has a winner, or before the threshold is met. On a win
    it records the winner once, updates win/loss stats, and announces it in chat.

    Returns the winning Player, or None.
    """
    if game.lockout_mode != LockoutMode.lockout or game.winner_id is not None:
        return None

    # Majority of the board; derived so it holds for any board size.
    threshold = game.size * game.size // 2 + 1

    confirmed_count = Square.objects.filter(
        game=game, claimed_by=player, claim_status='confirmed').count()
    if confirmed_count < threshold:
        return None

    with transaction.atomic():
        game.winner = player
        game.save(update_fields=['winner'])
        _record_win_loss(game, player)

    create_system_chat_message(
        player, game.room,
        f"{player.name} reached {threshold} goals and won the game!")

    # Transient celebration signal for the winner pop-up (the chat message
    # above is the persistent record; this drives the confetti overlay).
    from bingosync.publish import _publish_json
    _publish_json({
        "type": "game_won",
        "winner": player.name,
        "goals": threshold,
    }, game.room)
    return player


def _record_win_loss(game, winner):
    """Give the winner a win and every other logged-in Player a loss.

    Only Player-role participants with a linked account are scored; spectators,
    counters, and the gamemaster are not.
    """
    scored_players = Player.objects.filter(
        room=game.room, role=Role.PLAYER).exclude(user__isnull=True)
    for scored in scored_players:
        field = 'wins' if scored.id == winner.id else 'losses'
        User.objects.filter(pk=scored.user_id).update(**{field: F(field) + 1})


def _board_lines(size):
    """Every winning line on a size x size board as (key, [slot, ...]).

    Keys are stable ("row-0", "col-3", "diag-main", "diag-anti") so they can be
    stored and matched across calls. Slots are 1-indexed to match Square.slot.
    """
    lines = []
    for r in range(size):
        lines.append((f"row-{r}", [r * size + c + 1 for c in range(size)]))
    for c in range(size):
        lines.append((f"col-{c}", [r * size + c + 1 for r in range(size)]))
    lines.append(("diag-main", [i * size + i + 1 for i in range(size)]))
    lines.append(("diag-anti", [i * size + (size - 1 - i) + 1 for i in range(size)]))
    return lines


def check_and_record_bingos(game, player):
    """Credit any newly completed lines for `player` and count them as bingos.

    A line counts only when all of its squares are confirmed in the player's
    color (pending/under-review/rejected claims don't count), and each line is
    credited exactly once via the CompletedLine unique constraint. Increments
    the player's total_bingos_completed. Applies in both lockout and
    non-lockout. Returns the number of newly completed lines.
    """
    if not player or player.is_spectator:
        return 0

    player_color = player.color
    confirmed_slots = {
        square.slot
        for square in Square.objects.filter(game=game, claim_status='confirmed')
        if player_color in square.color.colors
    }

    already = set(
        CompletedLine.objects.filter(game=game, player=player)
        .values_list('line', flat=True))

    new_lines = [
        CompletedLine(game=game, player=player, line=key)
        for key, slots in _board_lines(game.size)
        if key not in already and all(slot in confirmed_slots for slot in slots)
    ]
    if not new_lines:
        return 0

    CompletedLine.objects.bulk_create(new_lines, ignore_conflicts=True)
    if player.user_id:
        User.objects.filter(pk=player.user_id).update(
            total_bingos_completed=F('total_bingos_completed') + len(new_lines))
    return len(new_lines)


def _record_square_marked(player):
    """Count one confirmed square mark toward the player's lifetime total."""
    if player and player.user_id:
        User.objects.filter(pk=player.user_id).update(
            total_squares_marked=F('total_squares_marked') + 1)


def _record_game_played(room):
    """Credit a completed game to each logged-in Player in the room.

    Called when a new card replaces the current game, so the game that just
    ended counts once for every Player who was in the room. Spectators,
    counters, and the gamemaster are not credited.
    """
    user_ids = (
        Player.objects.filter(room=room, role=Role.PLAYER)
        .exclude(user__isnull=True)
        .values_list('user_id', flat=True))
    User.objects.filter(pk__in=list(user_ids)).update(
        total_games_played=F('total_games_played') + 1)


@handle_ratelimit
@ratelimit_authenticated_action
def assign_role(request):
    """Assign a role to a player in the room. Only Gamemaster can change roles."""
    data = parse_body_json_or_400(
        request,
        required_keys=[
            "room",
            "target_player_uuid",
            "new_role"])

    room = Room.get_for_encoded_uuid_or_404(data["room"])
    player = _get_session_player(request.session, room)

    # Check permission to assign roles
    if not check_permission(player, 'assign_roles'):
        return HttpResponseForbidden(
            "You do not have permission to assign roles.")

    # Get the target player
    try:
        target_player = Player.get_for_encoded_uuid(data["target_player_uuid"])
    except Player.DoesNotExist:
        return HttpResponseBadRequest("Target player not found.")

    # Verify target player is in the same room
    if target_player.room != room:
        return HttpResponseForbidden("Target player is not in this room.")

    # Validate the new role
    from bingosync.models.enums import Role
    new_role = data["new_role"]
    valid_roles = [role[0] for role in Role.choices]
    if new_role not in valid_roles:
        return HttpResponseBadRequest(f"Invalid role: {new_role}")

    # Check if target player is logged in when changing to Player/Counter
    if new_role in [Role.PLAYER, Role.COUNTER]:
        if not target_player.user:
            return HttpResponseBadRequest(
                "Player must be logged in to become a Player or Counter. "
                "Only logged-in users can have these roles."
            )

    # Store old role for event
    old_role = target_player.role
    
    # RULE 1: Gamemaster role cannot be transferred after room creation
    # Prevent changing anyone TO Gamemaster
    if new_role == Role.GAMEMASTER:
        return HttpResponseBadRequest(
            "Gamemaster role can only be assigned at room creation. "
            "It cannot be transferred to another user."
        )
    
    # RULE 2: Gamemaster cannot change their own role
    # (Gamemaster role is permanent once assigned)
    if player.role == Role.GAMEMASTER and target_player.uuid == player.uuid:
        return HttpResponseBadRequest(
            "Gamemaster cannot change their own role. "
            "The Gamemaster role is permanent and cannot be transferred."
        )
    
    # RULE 3: Gamemaster cannot be changed to another role by anyone
    # (This prevents GM from being demoted by themselves or others)
    if old_role == Role.GAMEMASTER:
        return HttpResponseBadRequest(
            "Gamemaster role cannot be changed. "
            "The Gamemaster role is permanent and cannot be transferred."
        )

    # Normal role change (Player <-> Counter <-> Spectator)
    with transaction.atomic():
        target_player.role = new_role

        # If changing to/from Counter, clear monitoring_player
        if new_role != Role.COUNTER:
            target_player.monitoring_player = None

        target_player.save()

        # Create role change event
        role_change_event = RoleChangeEvent(
            player=player,
            player_color_value=player.color.value,
            target_player=target_player,
            old_role=old_role,
            new_role=new_role
        )
        role_change_event.save()
        
        # Create system chat message
        role_display_names = {
            Role.GAMEMASTER: "Gamemaster",
            Role.PLAYER: "Player",
            Role.COUNTER: "Counter",
            Role.SPECTATOR: "Spectator"
        }
        message = f"{target_player.name} has been assigned the {role_display_names.get(new_role, new_role)} role"
        create_system_chat_message(player, room, message)

    # Broadcast the role change
    publish_role_change_event(role_change_event)

    return HttpResponse("Role changed successfully")




@handle_ratelimit
@ratelimit_authenticated_action
def remove_player(request):
    """Remove a player from the room. Only Gamemaster can remove players."""
    data = parse_body_json_or_400(
        request,
        required_keys=[
            "room",
            "target_player_uuid"])

    room = Room.get_for_encoded_uuid_or_404(data["room"])
    player = _get_session_player(request.session, room)

    # Check permission to remove players
    if not check_permission(player, 'remove_players'):
        return HttpResponseForbidden(
            "You do not have permission to remove players.")

    # Get the target player
    try:
        target_player = Player.get_for_encoded_uuid(data["target_player_uuid"])
    except Player.DoesNotExist:
        return HttpResponseBadRequest("Target player not found.")

    # Verify target player is in the same room
    if target_player.room != room:
        return HttpResponseForbidden("Target player is not in this room.")

    # Prevent removing yourself
    if target_player.uuid == player.uuid:
        return HttpResponseBadRequest("You cannot remove yourself from the room.")

    # Create disconnection event before removing
    from bingosync.models.events import ConnectionEvent
    disconnected_event = ConnectionEvent.make_disconnected_event(target_player)
    disconnected_event.save()

    # Broadcast the disconnection
    from bingosync.publish import publish_connection_event
    publish_connection_event(disconnected_event)

    # Remove the player
    target_player.delete()

    # Update room active status
    # Note: Room can continue without Gamemaster until all players/counters disconnect
    room.update_active()

    return HttpResponse("Player removed successfully")


@handle_ratelimit
@ratelimit_authenticated_action
def assign_counter(request):
    """Assign a counter to monitor a specific player. 
    
    Can be called by:
    - Gamemaster: to assign any counter to any player
    - Counter: to assign themselves to a player
    """
    data = parse_body_json_or_400(
        request,
        required_keys=[
            "room",
            "counter_player_uuid",
            "monitored_player_uuid"])

    room = Room.get_for_encoded_uuid_or_404(data["room"])
    player = _get_session_player(request.session, room)

    # Get the counter player
    try:
        counter_player = Player.get_for_encoded_uuid(data["counter_player_uuid"])
    except Player.DoesNotExist:
        return HttpResponseBadRequest("Counter player not found.")

    # Verify counter player is in the same room
    if counter_player.room != room:
        return HttpResponseForbidden("Counter player is not in this room.")

    # Verify counter player has Counter role
    if counter_player.role != Role.COUNTER:
        return HttpResponseBadRequest("Player must have Counter role to be assigned as a counter.")

    # Get the monitored player (can be null for unassignment)
    monitored_player = None
    monitored_player_uuid = data.get("monitored_player_uuid")
    
    if monitored_player_uuid and monitored_player_uuid != "null":
        try:
            monitored_player = Player.get_for_encoded_uuid(monitored_player_uuid)
        except Player.DoesNotExist:
            return HttpResponseBadRequest("Monitored player not found.")

        # Verify monitored player is in the same room
        if monitored_player.room != room:
            return HttpResponseForbidden("Monitored player is not in this room.")

        # Verify monitored player is a Player (not spectator, counter, or gamemaster)
        if monitored_player.role != Role.PLAYER:
            return HttpResponseBadRequest("Can only assign counters to players with Player role.")

    # Check permissions
    # Gamemaster can assign any counter to any player
    # Counter can assign themselves to any player
    is_gamemaster = check_permission(player, 'assign_roles')
    is_self_assignment = (counter_player.uuid == player.uuid and player.role == Role.COUNTER)
    
    if not (is_gamemaster or is_self_assignment):
        return HttpResponseForbidden(
            "You do not have permission to assign counters. "
            "Only Gamemaster can assign counters, or Counters can assign themselves.")

    # Perform the assignment
    with transaction.atomic():
        counter_player.monitoring_player = monitored_player
        counter_player.save()

        # Create counter assignment event
        counter_assignment_event = CounterAssignmentEvent(
            player=player,
            player_color_value=player.color.value,
            counter_player=counter_player,
            monitored_player=monitored_player
        )
        counter_assignment_event.save()
        
        # Create system chat message
        if monitored_player:
            message = f"{counter_player.name} is now monitoring {monitored_player.name}'s claims"
        else:
            message = f"{counter_player.name} is no longer monitoring any player"
        create_system_chat_message(player, room, message, is_counter_message=True)

    # Broadcast the counter assignment
    publish_counter_assignment_event(counter_assignment_event)

    return HttpResponse("Counter assigned successfully")


@handle_ratelimit
@ratelimit_authenticated_action
def review_claim(request):
    """
    Counter reviews a claim with three options: under_review, confirm, or reject.
    
    Actions:
    - under_review: Mark claim for later review (square stays marked, pending)
    - confirm: Approve the claim (square permanently marked)
    - reject: Deny the claim and remove the marking
    """
    data = parse_body_json_or_400(
        request,
        required_keys=[
            "room",
            "slot",
            "action"])

    room = Room.get_for_encoded_uuid_or_404(data["room"])
    counter = _get_session_player(request.session, room)

    # Verify the player is a counter
    if counter.role != Role.COUNTER:
        return HttpResponseForbidden("Only counters can review claims.")

    # Get the square
    game = room.current_game
    slot = int(data["slot"])
    
    try:
        square = game.squares[slot - 1]
    except IndexError:
        return HttpResponseBadRequest(f"Invalid slot: {slot}")

    # Verify the square has a claim to review
    if not square.claimed_by:
        return HttpResponseBadRequest("This square has no claim to review.")

    # Verify the counter is assigned to the player who made the claim
    if square.claimed_by.counters.filter(id=counter.id).exists():
        # Counter is assigned to this player
        pass
    else:
        return HttpResponseForbidden(
            "You can only review claims from players you are monitoring.")

    # Validate action
    action = data["action"]
    valid_actions = ['under_review', 'confirm', 'reject']
    if action not in valid_actions:
        return HttpResponseBadRequest(
            f"Invalid action: {action}. Must be one of: {', '.join(valid_actions)}")

    # Perform the review action
    with transaction.atomic():
        reviewed_player = square.claimed_by
        
        if action == 'under_review':
            # Counter wants to review this later
            square.claim_status = 'under_review'
            square.reviewed_by = counter
            square.save()
            message = f"{counter.name} is reviewing {square.goal}"
            
        elif action == 'confirm':
            # Counter approves the claim
            square.claim_status = 'confirmed'
            square.reviewed_by = counter
            square.save()
            message = f"{counter.name} confirmed {reviewed_player.name}'s claim on {square.goal}"
            
        elif action == 'reject':
            # Counter rejects the claim - remove the color
            square_color = square.color
            square_color.remove(reviewed_player.color)
            square.color = square_color
            square.claim_status = 'rejected'
            square.reviewed_by = counter
            square.claimed_by = None  # Clear claimed_by on rejection
            square.save()
            message = f"{counter.name} rejected {reviewed_player.name}'s claim on {square.goal}"

        # Create claim review event
        claim_review_event = ClaimReviewEvent(
            player=counter,
            player_color_value=counter.color.value,
            square=square,
            action=action,
            reviewed_player=reviewed_player
        )
        claim_review_event.save()
        
        # Create system chat message
        create_system_chat_message(counter, room, message, is_counter_message=True)

    # Broadcast the claim review
    from bingosync.publish import publish_claim_review_event
    publish_claim_review_event(claim_review_event)

    # Confirming a claim can push the reviewed player over the lockout
    # threshold and/or complete one or more bingos.
    if action == 'confirm':
        _record_square_marked(reviewed_player)
        check_and_record_lockout_win(game, reviewed_player)
        check_and_record_bingos(game, reviewed_player)

    return HttpResponse("Claim reviewed successfully")




@handle_ratelimit
@ratelimit_login
def join_room_api(request):
    # grab data from input json
    try:
        raw_data = parse_body_json_or_400(
            request, required_keys=[
                "room", "nickname", "password"])
    except InvalidRequestJsonError as e:
        return JsonResponse({"error": str(e)})

    room = Room.get_for_encoded_uuid_or_404(raw_data["room"])

    # use a JoinRoomForm to share validation with the regular path
    form_data = {
        "encoded_room_uuid": room.encoded_uuid,
        "player_name": raw_data["nickname"],
        "passphrase": raw_data["password"],
        "role": raw_data.get("role", Role.PLAYER),
    }
    join_form = JoinRoomForm(data=form_data, room=room, user=request.user)
    if join_form.is_valid():
        try:
            # Pass the authenticated user to create_player
            user = request.user if request.user.is_authenticated else None
            player = join_form.create_player(user=user)
            _save_session_player(request.session, player)
            # Return socket_key directly in JSON response
            socket_key = _create_temporary_socket_key(player)
            return JsonResponse({"socket_key": socket_key})
        except ValidationError as e:
            return JsonResponse({"error": str(e)}, status=400)
    else:
        return HttpResponse(
            join_form.errors.as_json(),
            content_type="application/json",
            status=400)


def get_socket_key(request, encoded_room_uuid):
    room = Room.get_for_encoded_uuid_or_404(encoded_room_uuid)
    player = _get_session_player(request.session, room)
    data = {
        "socket_key": _create_temporary_socket_key(player),
    }
    return JsonResponse(data)


@csrf_exempt
@require_internal_api_secret
def user_connected(request, encoded_player_uuid):
    player = Player.get_for_encoded_uuid(encoded_player_uuid)
    if player is not ANON_PLAYER:
        connection_event = ConnectionEvent.atomically_connect(player)
        publish_connection_event(connection_event)
    return HttpResponse()

# TODO: add authentication to limit this route to tornado


@csrf_exempt
@require_internal_api_secret
def user_disconnected(request, encoded_player_uuid):
    player = Player.get_for_encoded_uuid(encoded_player_uuid)
    if player is not ANON_PLAYER:
        connection_event = ConnectionEvent.atomically_disconnect(player)
        publish_connection_event(connection_event)

        # Clear current_room for authenticated users to allow joining other rooms
        if player.user and player.user.current_room == player.room:
            player.user.current_room = None
            player.user.save()

        # Note: Room can continue without Gamemaster until all players/counters disconnect

    return HttpResponse()


@require_internal_api_secret
def check_socket_key(request, socket_key):
    try:
        kind, encoded_player_uuid = _get_temporary_socket_player_uuid(
            socket_key)
        if kind == "room":
            player = ANON_PLAYER
            room = Room.get_for_encoded_uuid(encoded_player_uuid)
        else:
            player = Player.get_for_encoded_uuid(encoded_player_uuid)
            room = player.room
        json_response = {
            "room": room.encoded_uuid,
            "player": player.encoded_uuid
        }
        return JsonResponse(json_response)
    except NotAuthenticatedError:
        raise Http404("Invalid socket key")


def reconcile_connections(request):
    from bingosync.util import get_internal_api_headers
    connected_url = SOCKETS_PUBLISH_URL + "/connected"
    response = requests.get(connected_url, headers=get_internal_api_headers())
    connected_rooms = response.json()

    active_rooms = Room.get_listed_rooms()
    for room in active_rooms:
        connected_player_uuids = connected_rooms.get(room.encoded_uuid, [])
        for player in room.connected_players:
            if player.encoded_uuid not in connected_player_uuids:
                ConnectionEvent.atomically_disconnect(player)
        room.update_active()

    return HttpResponse()


def goal_converter(request):
    if request.method == "POST":
        form = GoalListConverterForm(request.POST)
        if form.is_valid():
            goal_list_str = form.get_goal_list()
            response = HttpResponse(
                goal_list_str, content_type="application/json")
            response['Content-Disposition'] = 'attachment; filename="goal-list.js"'
            return response
        return render(request, "bingosync/convert.html", {"form": form})
    else:
        form = GoalListConverterForm.get()

    return render(request, "bingosync/convert.html", {"form": form})


def jstests(request):
    return render(request, "bingosync/tests/jstest.html", {})


# Helpers for interacting with sessions

AUTHORIZED_ROOMS = 'authorized_rooms'


class NotAuthenticatedError(Exception):
    pass


def _get_session_player(session, room):
    try:
        encoded_player_uuid = session[AUTHORIZED_ROOMS][room.encoded_uuid]
        return Player.get_for_encoded_uuid(encoded_player_uuid)
    except KeyError:
        raise NotAuthenticatedError()


def _clear_session_player(session, room):
    # have to set the session this way so that it saves properly
    authorized_rooms = session.get(AUTHORIZED_ROOMS, {})
    try:
        del authorized_rooms[room.encoded_uuid]
    except KeyError:
        logger.warn("Attempted to double-disconnect from room: %r", room)
    session[AUTHORIZED_ROOMS] = authorized_rooms


def _save_session_player(session, player):
    # have to set the session this way so that it saves properly
    authorized_rooms = session.get(AUTHORIZED_ROOMS, {})
    authorized_rooms[player.room.encoded_uuid] = player.encoded_uuid
    session[AUTHORIZED_ROOMS] = authorized_rooms


def _create_temporary_socket_key(player):
    temporary_socket_key = generate_encoded_uuid()
    uuid = player.encoded_uuid
    cache.set(temporary_socket_key, ("player", uuid))
    return temporary_socket_key


def _create_anon_socket_key(room):
    temporary_socket_key = generate_encoded_uuid()
    uuid = room.encoded_uuid
    cache.set(temporary_socket_key, ("room", uuid))
    return temporary_socket_key


def _get_temporary_socket_player_uuid(temporary_socket_key):
    encoded_player_uuid = cache.get(temporary_socket_key)
    if encoded_player_uuid:
        return encoded_player_uuid
    else:
        raise NotAuthenticatedError()


# Helpers for parsing request input

class InvalidRequestJsonError(Exception):
    pass


def parse_body_json_or_400(request, *, required_keys=[]):
    try:
        data = json.loads(request.body.decode("utf8"))
    except json.JSONDecodeError:
        raise InvalidRequestJsonError("Request body was not valid JSON.")

    for key in required_keys:
        if key not in data:
            raise InvalidRequestJsonError(
                "Request body \""
                + str(data)
                + "\" missing key: '"
                + str(key)
                + "'"
            )

    return data
