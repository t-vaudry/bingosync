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
    BASE_DJANGO_URL = f"http+unix://{urllib.parse.quote_plus(os.environ['HTTP_SOCK'])}/"
else:
    BASE_DJANGO_URL = f"http://{os.environ['DOMAIN']}/" if IS_PROD else "http://localhost:8000/"
BASE_API_URL = BASE_DJANGO_URL + "api/"

SOCKET_VERIFICATION_URL = BASE_API_URL + "socket/"
CONNECTION_URL = BASE_API_URL + "connected/"
DISCONNECTION_URL = BASE_API_URL + "disconnected/"

PING_PERIOD_SECONDS = 5
PING_PERIOD_MILLIS = PING_PERIOD_SECONDS * 1000
TIMEOUT_THRESHOLD = datetime.timedelta(seconds=60)

DEFAULT_RETRY_COUNT = 5

# whether we should clean up the broadcast sockets dictionary as people disconnect
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
            return self.resolver.resolve(host, port, *args, **kwargs)
resolver = UnixSocketResolver(resolver=Resolver())
AsyncHTTPClient.configure(None, resolver=resolver)

headers = {'Host': os.environ['DOMAIN'] if IS_PROD else 'localhost'}

def load_player_data(socket_key):
    response = requests.get(SOCKET_VERIFICATION_URL + socket_key, headers=headers)
    response_json = response.json()
    room_uuid = response_json["room"]
    player_uuid = response_json["player"]
    return room_uuid, player_uuid

def post_player_connection(player_uuid):
    ping_with_retry(CONNECTION_URL + player_uuid)

def post_player_disconnection(player_uuid):
    ping_with_retry(DISCONNECTION_URL + player_uuid)

def ping_with_retry(url, retry_count=DEFAULT_RETRY_COUNT):
    def retry_callback(response):
        if response.error:
            print("Response error:", response.error, "for url:", url)
            print("Retries left:", retry_count - 1)
            ping_with_retry(url, retry_count - 1)

    if retry_count <= 0:
        print("Ran out of retries, for url '" + url + "', giving up.")

    client = AsyncHTTPClient()
    client.fetch(url.replace('http+unix://', 'http://'), retry_callback, headers=headers)

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
    
    def __init__(self, max_connections=WS_RATE_LIMIT_CONNECTIONS, window_seconds=WS_RATE_LIMIT_WINDOW):
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

    @property
    def all_sockets(self):
        for room_sockets in self.sockets_by_room.values():
            for player_sockets in room_sockets.values():
                for socket in player_sockets:
                    yield socket

    def log_sockets(self, message=None):
        if message:
            print(message)
        pprint.pprint(format_defaultdict(self.sockets_by_room))
        print()

    def send_all(self, message):
        print("sending message:", repr(message), "to", len(list(self.all_sockets)), "sockets")
        for socket in self.all_sockets:
            try:
                socket.send(message)
            except:
                pass

    def ping_all(self):
        for socket in list(self.all_sockets):
            try:
                socket.ping("boop".encode("utf8"))
            except tornado.websocket.WebSocketClosedError:
                print("pinged socket that was already closed, unregistering", socket)
                self.unregister(socket)

    def kill_dead_sockets(self):
        threshold = datetime.datetime.now() - TIMEOUT_THRESHOLD
        for socket in self.all_sockets:
            if socket.last_pong < threshold:
                print("closing dead socket:", socket)
                try:
                    socket.close()
                except tornado.websocket.WebSocketClosedError:
                    print("socket already closed, attempting to unregister", socket)
                    self.unregister(socket)

    def send_to_room(self, room_uuid, message):
        room_sockets = self.sockets_by_room[room_uuid]
        for player_sockets in room_sockets.values():
            for socket in player_sockets:
                socket.send(message)

    def register(self, room_uuid, player_uuid, socket):
        self.log_sockets("registering socket...")
        if not self.sockets_by_room[room_uuid][player_uuid]:
            print("posting connect")
            post_player_connection(player_uuid)
        self.sockets_by_room[room_uuid][player_uuid].add(socket)
        self.log_sockets("registered")

    def unregister(self, socket):
        self.log_sockets("unregistering socket...")
        for room_uuid in self.sockets_by_room:
            room_sockets = self.sockets_by_room[room_uuid]
            for player_uuid in room_sockets:
                player_sockets = room_sockets[player_uuid]
                if player_sockets:
                    player_sockets.discard(socket)
                    if not player_sockets:
                        print("posting disconnect", player_uuid)
                        post_player_disconnection(player_uuid)
                        if CLEANUP_SOCKETS_DICT_ON_DISCONNECT:
                            del room_sockets[player_uuid]
                            break
            if not room_sockets:
                if CLEANUP_SOCKETS_DICT_ON_DISCONNECT:
                    print("room closed:", room_uuid)
                    del self.sockets_by_room[room_uuid]
                    break
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
        data = {room: list(players.keys()) for room, players in ROUTER.sockets_by_room.items()}
        self.write(json.dumps(data))


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
            print(f"WebSocket connection rejected: Origin '{origin}' (host: {origin_host}) not in ALLOWED_HOSTS. IP: {ip_address}")
            return False
            
        except Exception as e:
            # Log parsing errors and reject the connection
            ip_address = self.request.remote_ip
            print(f"WebSocket connection rejected: Failed to parse origin '{origin}'. Error: {e}. IP: {ip_address}")
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
            print(f"Rate limit exceeded for WebSocket connection from {ip_address}")
            self.close(code=1008, reason="Rate limit exceeded. Too many connection attempts.")
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
            self.send(json.dumps({"type": "error", "error": "unable to authenticate, try refreshing", "exception": str(e)}))

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

if __name__ == "__main__":
    print("Starting application!")
    if SOCK is None:
        print("Listening on port: " + str(PORT))
        application.listen(PORT)
    else:
        if bind_unix_socket is None:
            raise RuntimeError("Unix sockets are not supported on this platform (Windows)")
        print("Listening on socket: " + str(SOCK))
        server = HTTPServer(application)
        mysock = bind_unix_socket(SOCK, mode=0o666)
        server.add_socket(mysock)
    io_loop = tornado.ioloop.IOLoop.current()
    pinger = tornado.ioloop.PeriodicCallback(periodic_ping, PING_PERIOD_MILLIS)
    pinger.start()
    io_loop.start()
