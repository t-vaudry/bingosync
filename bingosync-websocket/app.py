import tornado.ioloop
import tornado.web
import tornado.websocket
from tornado.httpclient import AsyncHTTPClient
from tornado.httpserver import HTTPServer
from tornado.netutil import Resolver
try:
    from tornado.netutil import bind_unix_socket
except ImportError:
    # bind_unix_socket not available on Windows
    bind_unix_socket = None
import urllib.parse

from collections import defaultdict
import traceback
import datetime
import json
import requests
import pprint
import os
import socket
import time

import requests_unixsocket
requests_unixsocket.monkeypatch()

IS_PROD = os.getenv('DEBUG', '').lower() not in ('1', 'yes')
PORT = int(os.getenv('WS_PORT', '8888'))
SOCK = os.getenv('WS_SOCK', None)

# Allowed hosts for WebSocket origin validation
# Mirrors Django's ALLOWED_HOSTS configuration
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
if "DOMAIN" in os.environ:
    domain = os.environ["DOMAIN"]
    ALLOWED_HOSTS.append(domain)

# Internal API authentication secret
# Used to authenticate requests from Django to Tornado
INTERNAL_API_SECRET = os.getenv('INTERNAL_API_SECRET')
if not INTERNAL_API_SECRET:
    raise ValueError(
        "INTERNAL_API_SECRET environment variable is required. "
        "This secret is used to authenticate internal API calls from Django. "
        "Generate a secure random string (32+ characters) using: "
        "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
    )
if len(INTERNAL_API_SECRET) < 32:
    raise ValueError(
        "INTERNAL_API_SECRET must be at least 32 characters long for security. "
        "Current length: " + str(len(INTERNAL_API_SECRET))
    )

if 'HTTP_SOCK' in os.environ:
    BASE_DJANGO_URL = (
        f"http+unix://{urllib.parse.quote_plus(os.environ['HTTP_SOCK'])}/")
else:
    # Talk to Django directly (in Docker, the service name). Requests still
    # carry Host: DOMAIN in production so Django's ALLOWED_HOSTS accepts
    # them; they never leave the internal network.
    DJANGO_HOST = os.getenv('DJANGO_INTERNAL_HOST', 'localhost:8000')
    BASE_DJANGO_URL = f"http://{DJANGO_HOST}/"
BASE_API_URL = BASE_DJANGO_URL + "api/"

SOCKET_VERIFICATION_URL = BASE_API_URL + "socket/"
CONNECTION_URL = BASE_API_URL + "connected/"
DISCONNECTION_URL = BASE_API_URL + "disconnected/"
RECONCILE_URL = BASE_API_URL + "reconcile"

# Ask Django to drop players with no live socket: shortly after startup (a
# restart forgets every connection) and then periodically.
RECONCILE_STARTUP_DELAY_SECONDS = 15
RECONCILE_PERIOD_SECONDS = 60

PING_PERIOD_SECONDS = 5
PING_PERIOD_MILLIS = PING_PERIOD_SECONDS * 1000
# A socket that hasn't answered pings for this long is closed (and its player
# disconnected after the grace period). Covers connections that vanish
# without closing, e.g. a laptop going to sleep or a phone losing signal.
TIMEOUT_THRESHOLD = datetime.timedelta(seconds=20)

# How long a player's last socket can be gone before they're reported as
# disconnected. Reloading the page closes the old socket just before the new
# one opens; reporting that at once would announce a disconnect the new page
# receives for itself (and treats as being removed from the room).
DISCONNECT_GRACE_SECONDS = 5

DEFAULT_RETRY_COUNT = 5

# whether we should clean up the broadcast sockets dictionary as people
# disconnect
CLEANUP_SOCKETS_DICT_ON_DISCONNECT = True

# Rate limiting configuration for WebSocket connections
# 20 connections per minute per IP address
WS_RATE_LIMIT_CONNECTIONS = 20
WS_RATE_LIMIT_WINDOW = 60  # seconds

# https://lovelace.cluster.earlham.edu/mounts/lovelace/software/anaconda3/envs/qiime2-amplicon-2024.2/lib/python3.8/site-packages/jupyter_server/utils.py


class UnixSocketResolver(Resolver):
    """A resolver that routes HTTP requests to unix sockets
    in tornado HTTP clients.
    Due to constraints in Tornados' API, the scheme of the
    must be `http` (not `http+unix`). Applications should replace
    the scheme in URLS before making a request to the HTTP client.
    """

    def initialize(self, resolver):
        self.resolver = resolver

    def close(self):
        self.resolver.close()

    async def resolve(self, host, port, *args, **kwargs):
        if '%2F' in host:
            return [(socket.AF_UNIX, urllib.parse.unquote_plus(host))]
        else:
            return await self.resolver.resolve(host, port, *args, **kwargs)


resolver = UnixSocketResolver(resolver=Resolver())
AsyncHTTPClient.configure(None, resolver=resolver)

headers = {'Host': os.environ['DOMAIN'] if IS_PROD else 'localhost'}


def load_player_data(socket_key):
    response = requests.get(
        SOCKET_VERIFICATION_URL + socket_key,
        headers={
            'Host': os.environ['DOMAIN'] if IS_PROD else 'localhost',
            'X-Internal-Secret': INTERNAL_API_SECRET
        })
    response_json = response.json()
    room_uuid = response_json["room"]
    player_uuid = response_json["player"]
    return room_uuid, player_uuid


def post_player_connection(player_uuid):
    ping_with_retry(CONNECTION_URL + player_uuid)


def post_player_disconnection(player_uuid):
    ping_with_retry(DISCONNECTION_URL + player_uuid)


def ping_with_retry(url, retry_count=DEFAULT_RETRY_COUNT):
    def on_response(future):
        error = future.exception()
        if error is None:
            return
        print("Response error:", error, "for url:", url)
        if retry_count <= 1:
            print("Ran out of retries, for url '" + url + "', giving up.")
            return
        print("Retries left:", retry_count - 1)
        tornado.ioloop.IOLoop.current().call_later(
            1, ping_with_retry, url, retry_count - 1)

    # Include internal API secret for authentication
    auth_headers = {
        'Host': os.environ['DOMAIN'] if IS_PROD else 'localhost',
        'X-Internal-Secret': INTERNAL_API_SECRET
    }

    future = AsyncHTTPClient().fetch(
        url.replace('http+unix://', 'http://'), headers=auth_headers)
    future.add_done_callback(on_response)


def format_defaultdict(ddict):
    if isinstance(ddict, defaultdict):
        return {key: format_defaultdict(ddict[key]) for key in ddict}
    else:
        return ddict


def validate_internal_request(request_handler):
    """
    Validate that a request comes from Django using the shared secret.

    Returns True if the request is authenticated, False otherwise.
    """
    auth_header = request_handler.request.headers.get('X-Internal-Secret')
    return auth_header == INTERNAL_API_SECRET


class InternalAPIHandler(tornado.web.RequestHandler):
    """
    Base handler for internal API endpoints that require authentication.

    Validates the X-Internal-Secret header before processing requests.
    """

    def prepare(self):
        """
        Called before each request method.

        Validates the internal API secret and returns 401 if invalid.
        """
        if not validate_internal_request(self):
            self.set_status(401)
            self.write({
                'error': 'Unauthorized',
                'message': 'Invalid or missing X-Internal-Secret header'
            })
            self.finish()
            # Prevent the actual request handler from running
            raise tornado.web.Finish()


class WebSocketRateLimiter:
    """
    Rate limiter for WebSocket connections.

    Tracks connection attempts per IP address and enforces a limit of
    20 connections per minute per IP.
    """

    def __init__(self, max_connections=WS_RATE_LIMIT_CONNECTIONS,
                 window_seconds=WS_RATE_LIMIT_WINDOW):
        self.max_connections = max_connections
        self.window_seconds = window_seconds
        # Dictionary mapping IP -> list of connection timestamps
        self.connection_attempts = defaultdict(list)

    def is_rate_limited(self, ip_address):
        """
        Check if an IP address has exceeded the rate limit.

        Returns True if rate limited, False otherwise.
        """
        now = time.time()

        # Clean up old connection attempts outside the window
        self.connection_attempts[ip_address] = [
            timestamp for timestamp in self.connection_attempts[ip_address]
            if now - timestamp < self.window_seconds
        ]

        # Check if we've exceeded the limit
        if len(self.connection_attempts[ip_address]) >= self.max_connections:
            return True

        # Record this connection attempt
        self.connection_attempts[ip_address].append(now)
        return False

    def cleanup_old_entries(self):
        """
        Periodically clean up old entries to prevent memory growth.
        Called by periodic callback.
        """
        now = time.time()
        ips_to_remove = []

        for ip_address, timestamps in self.connection_attempts.items():
            # Remove timestamps outside the window
            self.connection_attempts[ip_address] = [
                timestamp for timestamp in timestamps
                if now - timestamp < self.window_seconds
            ]

            # If no recent attempts, mark for removal
            if not self.connection_attempts[ip_address]:
                ips_to_remove.append(ip_address)

        # Remove IPs with no recent attempts
        for ip_address in ips_to_remove:
            del self.connection_attempts[ip_address]


# Global rate limiter instance
WS_RATE_LIMITER = WebSocketRateLimiter()


class SocketRouter:

    def __init__(self):
        self.sockets_by_room = defaultdict(lambda: defaultdict(set))
        # player_uuid -> (room_uuid, timeout handle) for a disconnect waiting
        # out the grace period (see DISCONNECT_GRACE_SECONDS)
        self.pending_disconnects = {}

    # Scheduling hooks (replaced in tests)
    def _call_later(self, delay, callback):
        return tornado.ioloop.IOLoop.current().call_later(delay, callback)

    def _cancel(self, handle):
        tornado.ioloop.IOLoop.current().remove_timeout(handle)

    @property
    def all_sockets(self):
        for room_sockets in self.sockets_by_room.values():
            for player_sockets in room_sockets.values():
                for ws in player_sockets:
                    yield ws

    def log_sockets(self, message=None):
        if message:
            print(message)
        pprint.pprint(format_defaultdict(self.sockets_by_room))
        print()

    def send_all(self, message):
        print("sending message:", repr(message), "to",
              len(list(self.all_sockets)), "sockets")
        for ws in self.all_sockets:
            try:
                ws.send(message)
            except Exception as e:
                print(f"Failed to send message to socket: {e}")

    def ping_all(self):
        for ws in list(self.all_sockets):
            try:
                ws.ping("boop".encode("utf8"))
            except tornado.websocket.WebSocketClosedError:
                print(
                    "pinged socket that was already closed, unregistering",
                    ws)
                self.unregister(ws)

    def kill_dead_sockets(self):
        threshold = datetime.datetime.now() - TIMEOUT_THRESHOLD
        # Iterate over a snapshot to avoid RuntimeError if unregister() mutates sockets_by_room
        for ws in list(self.all_sockets):
            if ws.last_pong < threshold:
                print("closing dead socket:", ws)
                try:
                    ws.close()
                except tornado.websocket.WebSocketClosedError:
                    print(
                        "socket already closed, attempting to unregister",
                        ws)
                    self.unregister(ws)

    def send_to_room(self, room_uuid, message):
        # .get, not [] -- indexing the defaultdict would leave an empty entry
        # behind for every room that gets a broadcast with nobody connected.
        room_sockets = self.sockets_by_room.get(room_uuid, {})
        for player_sockets in room_sockets.values():
            for ws in player_sockets:
                ws.send(message)

    def register(self, room_uuid, player_uuid, socket):
        self.log_sockets("registering socket...")
        pending = self.pending_disconnects.pop(player_uuid, None)
        if pending is not None:
            # Back within the grace period (e.g. a page reload): as far as
            # everyone else is concerned they never left.
            self._cancel(pending[1])
        elif not self.sockets_by_room[room_uuid][player_uuid]:
            print("posting connect")
            post_player_connection(player_uuid)
        self.sockets_by_room[room_uuid][player_uuid].add(socket)
        self.log_sockets("registered")

    def _disconnect_after_grace(self, room_uuid, player_uuid):
        def disconnect():
            self.pending_disconnects.pop(player_uuid, None)
            if not self.sockets_by_room.get(room_uuid, {}).get(player_uuid):
                print("posting disconnect", player_uuid)
                post_player_disconnection(player_uuid)

        previous = self.pending_disconnects.pop(player_uuid, None)
        if previous is not None:
            self._cancel(previous[1])
        self.pending_disconnects[player_uuid] = (
            room_uuid, self._call_later(DISCONNECT_GRACE_SECONDS, disconnect))

    def connected_players_by_room(self):
        """room_uuid -> player uuids that are connected, including anyone
        inside the disconnect grace period (they may be reloading the page).
        Django's reconcile disconnects players missing from this."""
        connected = defaultdict(set)
        for room_uuid, room_sockets in self.sockets_by_room.items():
            for player_uuid, player_sockets in room_sockets.items():
                if player_sockets:
                    connected[room_uuid].add(player_uuid)
        for player_uuid, (room_uuid, _) in self.pending_disconnects.items():
            connected[room_uuid].add(player_uuid)
        return {room: sorted(players) for room, players in connected.items()}

    def unregister(self, socket):
        self.log_sockets("unregistering socket...")
        # Walk every room (over snapshots, since entries are deleted along the
        # way). Stopping early at the first empty room used to leave a closed
        # socket registered, delaying the player's disconnect by up to a
        # minute.
        for room_uuid, room_sockets in list(self.sockets_by_room.items()):
            for player_uuid, player_sockets in list(room_sockets.items()):
                if socket not in player_sockets:
                    continue
                player_sockets.discard(socket)
                if not player_sockets:
                    print("player's last socket closed, disconnecting after grace period:", player_uuid)
                    self._disconnect_after_grace(room_uuid, player_uuid)
                    if CLEANUP_SOCKETS_DICT_ON_DISCONNECT:
                        del room_sockets[player_uuid]
            if not room_sockets and CLEANUP_SOCKETS_DICT_ON_DISCONNECT:
                print("room closed:", room_uuid)
                del self.sockets_by_room[room_uuid]
        self.log_sockets("unregistered")


ROUTER = SocketRouter()


class MainHandler(InternalAPIHandler):

    def get(self):
        self.write("Hello, world")

    def put(self):
        data = json.loads(self.request.body.decode("utf8"))
        room_uuid = data["room"]
        ROUTER.send_to_room(room_uuid, data)


class ConnectedHandler(InternalAPIHandler):

    def get(self):
        self.write(json.dumps(ROUTER.connected_players_by_room()))


class BroadcastWebSocket(tornado.websocket.WebSocketHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_pong = datetime.datetime.now()

    def __repr__(self):
        return "Socket(" + str(self.last_pong) + ")"

    def check_origin(self, origin):
        """
        Validate WebSocket connection origin against allowed hosts.

        Returns True if the origin is allowed, False otherwise.
        Logs rejected connections for security monitoring.
        """
        try:
            # Parse the origin URL to extract the hostname
            parsed_origin = urllib.parse.urlparse(origin)
            origin_host = parsed_origin.hostname

            # Check if the origin host is in ALLOWED_HOSTS
            if origin_host in ALLOWED_HOSTS:
                return True

            # Log rejected connection
            ip_address = self.request.remote_ip
            print(
                f"WebSocket connection rejected: Origin '{origin}' "
                f"(host: {origin_host}) not in ALLOWED_HOSTS. "
                f"IP: {ip_address}"
            )
            return False

        except Exception as e:
            # Log parsing errors and reject the connection
            ip_address = self.request.remote_ip
            print(
                f"WebSocket connection rejected: Failed to parse origin "
                f"'{origin}'. Error: {e}. IP: {ip_address}"
            )
            return False

    def open(self):
        """
        Called when a new WebSocket connection is opened.

        Checks rate limiting before allowing the connection.
        """
        # Get the client's IP address
        ip_address = self.request.remote_ip

        # Check if this IP is rate limited
        if WS_RATE_LIMITER.is_rate_limited(ip_address):
            print(
                f"Rate limit exceeded for WebSocket connection from {ip_address}")
            self.close(
                code=1008,
                reason="Rate limit exceeded. Too many connection attempts.")
            return

        print(f"WebSocket connection opened from {ip_address}")

    def send(self, message):
        try:
            self.write_message(message)
        except tornado.websocket.WebSocketClosedError:
            self.close()

    def on_pong(self, data):
        self.last_pong = datetime.datetime.now()

    def on_message(self, message):
        try:
            message_dict = json.loads(message)
            socket_key = message_dict["socket_key"]
            room_uuid, player_uuid = load_player_data(socket_key)
            ROUTER.register(room_uuid, player_uuid, self)
        except Exception as e:
            traceback.print_exc()
            self.send(json.dumps({"type": "error",
                                  "error": "unable to authenticate, try refreshing",
                                  "exception": str(e)}))

    def on_close(self):
        ROUTER.unregister(self)


application = tornado.web.Application([
    (r"/", MainHandler),
    (r"/connected", ConnectedHandler),
    (r"/broadcast", BroadcastWebSocket)
])


def periodic_ping():
    ROUTER.ping_all()
    ROUTER.kill_dead_sockets()
    WS_RATE_LIMITER.cleanup_old_entries()


def request_reconcile():
    """Ask Django to disconnect players we have no live socket for.

    Connections live only in this process's memory: after a restart (every
    deploy) nobody's disconnect was reported, so without this they'd stay
    "in the room" forever. See reconcile_connections in Django.
    """
    def report(future):
        try:
            future.result()
        except Exception as e:
            print("Reconcile request failed:", e)

    AsyncHTTPClient().fetch(
        RECONCILE_URL.replace('http+unix://', 'http://'),
        headers={
            'Host': os.environ['DOMAIN'] if IS_PROD else 'localhost',
            'X-Internal-Secret': INTERNAL_API_SECRET,
        }).add_done_callback(report)


if __name__ == "__main__":
    print("Starting application!")
    if SOCK is None:
        print("Listening on port: " + str(PORT))
        # Only nginx reaches this port; trust its X-Real-IP so rate limits
        # apply per client rather than to everyone at once.
        application.listen(PORT, xheaders=True)
    else:
        if bind_unix_socket is None:
            raise RuntimeError(
                "Unix sockets are not supported on this platform (Windows)")
        print("Listening on socket: " + str(SOCK))
        server = HTTPServer(application)
        mysock = bind_unix_socket(SOCK, mode=0o666)
        server.add_socket(mysock)
    io_loop = tornado.ioloop.IOLoop.current()
    pinger = tornado.ioloop.PeriodicCallback(periodic_ping, PING_PERIOD_MILLIS)
    pinger.start()
    io_loop.call_later(RECONCILE_STARTUP_DELAY_SECONDS, request_reconcile)
    reconciler = tornado.ioloop.PeriodicCallback(
        request_reconcile, RECONCILE_PERIOD_SECONDS * 1000)
    reconciler.start()
    io_loop.start()
