# Design Document: HP Bingo Platform Transformation

## Introduction

This document provides the technical design for transforming the Bingosync codebase into a specialized Harry Potter Chamber of Secrets bingo platform. The design addresses all 21 requirements while prioritizing security, performance, and maintainability.

## High-Level Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Nginx (Reverse Proxy)                │
│                    HTTP + WebSocket Traffic                  │
└────────────────┬────────────────────────┬───────────────────┘
                 │                        │
                 ▼                        ▼
┌────────────────────────────┐  ┌──────────────────────────┐
│     Django Application     │  │   Tornado WebSocket      │
│   (HTTP API + Templates)   │◄─┤      Server              │
│                            │  │  (Real-time Updates)     │
└────────────┬───────────────┘  └──────────┬───────────────┘
             │                              │
             │    ┌─────────────────────────┘
             │    │
             ▼    ▼
┌────────────────────────────┐  ┌──────────────────────────┐
│      PostgreSQL            │  │       Redis              │
│   (Primary Database)       │  │  (Cache + Sessions)      │
└────────────────────────────┘  └──────────────────────────┘
```

### Technology Stack

- **Backend**: Django 4.2 LTS (Python 3.11+)
- **WebSocket Server**: Tornado 6.x
- **Database**: PostgreSQL 15+
- **Cache**: Redis 7+
- **Web Server**: Nginx 1.24+
- **Frontend**: Bootstrap 5, Vanilla JavaScript
- **Deployment**: Docker Compose
- **Monitoring**: Sentry, Prometheus


## Database Schema Design

### Core Models

#### User Model
```python
class User(AbstractUser):
    """Persistent user account"""
    # Inherits: username, email, password, date_joined
    created_at = DateTimeField(auto_now_add=True)
    current_room = ForeignKey('Room', null=True, blank=True)  # Enforce 1 room at a time
    
    # Statistics
    total_games_played = IntegerField(default=0)
    total_squares_marked = IntegerField(default=0)
    total_bingos_completed = IntegerField(default=0)
    wins = IntegerField(default=0)  # In lockout mode
    losses = IntegerField(default=0)  # In lockout mode
```

#### Room Model
```python
class Room(Model):
    """Game session container"""
    uuid = UUIDField(primary_key=True, default=uuid4)
    name = CharField(max_length=255)
    creator = ForeignKey(User, related_name='created_rooms')
    created_date = DateTimeField(auto_now_add=True)
    hide_card = BooleanField(default=False)
    active = BooleanField(default=True)
    current_game = ForeignKey('Game', null=True)
    
    # Indexes
    class Meta:
        indexes = [
            Index(fields=['active']),
            Index(fields=['created_date']),
        ]
```

#### Game Model
```python
class Game(Model):
    """Bingo board instance"""
    room = ForeignKey(Room, related_name='games')
    seed = IntegerField()
    board_json = JSONField()  # 25-element array of objectives
    size = IntegerField(default=5)
    created_date = DateTimeField(auto_now_add=True)
    lockout_mode = CharField(max_length=20, choices=LockoutMode.choices())
    fog_of_war = BooleanField(default=False)
    
    # HP CoS specific - no game_type needed (always HP CoS)
```


#### Player Model
```python
class Player(Model):
    """Participant in a room"""
    user = ForeignKey(User, related_name='player_sessions')
    room = ForeignKey(Room, related_name='players')
    name = CharField(max_length=255)  # Display name in room
    color = CharField(max_length=20, choices=Color.choices())
    role = CharField(max_length=20, choices=Role.choices())  # GM, Player, Counter, Spectator
    is_spectator = BooleanField(default=False)  # Deprecated, use role
    joined_date = DateTimeField(auto_now_add=True)
    
    # Counter assignment
    monitoring_player = ForeignKey('self', null=True, blank=True, related_name='counters')
    
    class Meta:
        indexes = [
            Index(fields=['room', 'user']),
            Index(fields=['monitoring_player']),
        ]
        unique_together = [['room', 'user']]
```

#### Square Model
```python
class Square(Model):
    """Individual bingo square state"""
    game = ForeignKey(Game, related_name='squares')
    slot = IntegerField()  # 1-25
    colors = JSONField(default=list)  # List of color strings
    claim_status = CharField(max_length=20, default='none')  # none, under_review, confirmed, rejected
    claimed_by = ForeignKey(Player, null=True, related_name='claimed_squares')
    reviewed_by = ForeignKey(Player, null=True, related_name='reviewed_squares')
    
    class Meta:
        indexes = [
            Index(fields=['game', 'slot']),
        ]
        unique_together = [['game', 'slot']]
```

#### Event Model (Abstract Base)
```python
class Event(Model):
    """Base event for room history"""
    player = ForeignKey(Player, related_name='events')
    player_color = CharField(max_length=20)
    timestamp = DateTimeField(auto_now_add=True)
    event_type = CharField(max_length=50)
    
    class Meta:
        abstract = True
        indexes = [
            Index(fields=['timestamp']),
        ]
```


#### Concrete Event Models
```python
class GoalEvent(Event):
    """Square marked/unmarked"""
    slot = IntegerField()
    remove = BooleanField(default=False)
    claim_status = CharField(max_length=20, default='confirmed')  # under_review, confirmed, rejected

class ClaimReviewEvent(Event):
    """Counter reviews a claim"""
    slot = IntegerField()
    action = CharField(max_length=20)  # confirm, reject
    reviewed_player = ForeignKey(Player, related_name='claim_reviews')

class NewCardEvent(Event):
    """New board generated"""
    seed = IntegerField()
    hide_card = BooleanField()
    fog_of_war = BooleanField()

class RoleChangeEvent(Event):
    """Player role changed"""
    target_player = ForeignKey(Player, related_name='role_changes')
    old_role = CharField(max_length=20)
    new_role = CharField(max_length=20)
```

#### Achievement Models
```python
class Achievement(Model):
    """Achievement definition"""
    code = CharField(max_length=50, unique=True)
    name = CharField(max_length=255)
    description = TextField()
    category = CharField(max_length=50)  # milestone, pattern, speed
    criteria = JSONField()  # Flexible criteria definition
    icon = CharField(max_length=255, null=True)

class UserAchievement(Model):
    """User's earned achievements"""
    user = ForeignKey(User, related_name='achievements')
    achievement = ForeignKey(Achievement)
    earned_date = DateTimeField(auto_now_add=True)
    progress = JSONField(default=dict)  # For partial progress tracking
    
    class Meta:
        unique_together = [['user', 'achievement']]
```


## API Design

### REST Endpoints

#### Authentication
- `POST /api/auth/register` - Create new user account
- `POST /api/auth/login` - Login with username/password
- `POST /api/auth/logout` - Logout current user
- `POST /api/auth/password-reset` - Request password reset email
- `POST /api/auth/password-reset-confirm` - Confirm password reset with token

#### Rooms
- `GET /` - Homepage with room list
- `POST /api/rooms/create` - Create new room (requires auth)
- `GET /api/rooms/{uuid}` - Get room details
- `POST /api/rooms/{uuid}/join` - Join room (requires auth, checks current_room)
- `POST /api/rooms/{uuid}/leave` - Leave room
- `DELETE /api/rooms/{uuid}` - Delete room (GM only)

#### Game Actions
- `POST /api/rooms/{uuid}/new-card` - Generate new board (GM only)
- `POST /api/rooms/{uuid}/select` - Mark/unmark square (Player role)
- `POST /api/rooms/{uuid}/reveal-board` - Reveal fog of war (GM only)

#### Role Management
- `POST /api/rooms/{uuid}/assign-role` - Change player role (GM only)
- `POST /api/rooms/{uuid}/assign-counter` - Assign counter to player (GM only)
- `POST /api/rooms/{uuid}/remove-player` - Remove player from room (GM only)

#### Claim Review (Counter Role)
- `POST /api/rooms/{uuid}/review-claim` - Confirm or reject claim
  - Body: `{slot: int, action: "confirm"|"reject"}`

#### User Profile
- `GET /api/users/{username}` - Get user profile with statistics
- `GET /api/users/{username}/achievements` - Get user achievements
- `GET /api/users/{username}/history` - Get room history


### WebSocket Protocol

#### Connection
- URL: `ws://domain/websocket/{room_uuid}`
- Authentication: Session cookie or token in query param
- Origin validation against ALLOWED_HOSTS

#### Message Types (Server → Client)

```javascript
// Goal marked/unmarked
{
  type: "goal",
  player: "PlayerName",
  slot: 12,
  color: "red",
  remove: false,
  claim_status: "under_review"  // or "confirmed", "rejected"
}

// Claim reviewed by counter
{
  type: "claim_review",
  counter: "CounterName",
  player: "PlayerName",
  slot: 12,
  action: "confirm",  // or "reject"
  color: "red"
}

// New board generated
{
  type: "new_card",
  board: [...],  // 25 objectives
  seed: 12345,
  fog_of_war: true
}

// Role changed
{
  type: "role_change",
  player: "PlayerName",
  old_role: "player",
  new_role: "counter"
}

// Player joined/left
{
  type: "player_join",
  player: "PlayerName",
  color: "blue",
  role: "player"
}

// Achievement unlocked
{
  type: "achievement",
  player: "PlayerName",
  achievement: "First Bingo",
  description: "Complete your first bingo"
}
```


## Security Architecture

### Authentication & Authorization

#### Django Session-Based Auth
- Use Django's built-in authentication system
- PBKDF2 password hashing (default)
- Session cookies with secure flags in production:
  - `SESSION_COOKIE_SECURE = True`
  - `SESSION_COOKIE_HTTPONLY = True`
  - `SESSION_COOKIE_SAMESITE = 'Lax'`
  - `CSRF_COOKIE_SECURE = True`

#### Role-Based Access Control
```python
class RolePermissions:
    GAMEMASTER = {
        'mark_square': True,  # If also player
        'generate_board': True,
        'reveal_fog': True,
        'assign_roles': True,
        'remove_players': True,
        'delete_room': True,
    }
    
    PLAYER = {
        'mark_square': True,
        'view_board': True,
        'chat': True,
    }
    
    COUNTER = {
        'view_board': True,
        'review_claims': True,  # Only for assigned player
        'chat': True,
    }
    
    SPECTATOR = {
        'view_board': True,
        'chat': True,
    }
```

### Django-Tornado Authentication

#### Shared Secret Approach
```python
# settings.py
INTERNAL_API_SECRET = env('INTERNAL_API_SECRET')  # 32+ char random string

# Tornado validates requests from Django
def validate_internal_request(request):
    auth_header = request.headers.get('X-Internal-Secret')
    return auth_header == INTERNAL_API_SECRET
```


### Rate Limiting

```python
# Using django-ratelimit
from django_ratelimit.decorators import ratelimit

# Public endpoints
@ratelimit(key='ip', rate='10/m', method='POST')  # Login attempts
@ratelimit(key='ip', rate='5/m', method='POST')   # Registration
@ratelimit(key='user', rate='100/h', method='POST')  # Authenticated actions

# WebSocket connections
@ratelimit(key='ip', rate='20/m')  # Connection attempts
```

### Security Headers

```python
# settings.py
SECURE_SSL_REDIRECT = True  # Production only
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# CSP Header
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")  # Minimize inline scripts
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
```

### Input Validation

```python
# All user inputs validated through Django forms
class RoomForm(forms.Form):
    room_name = forms.CharField(max_length=255, validators=[validate_room_name])
    seed = forms.IntegerField(min_value=1, max_value=999999)
    
    def clean_room_name(self):
        name = self.cleaned_data['room_name']
        # Apply profanity filter
        return FilteredPattern.filter_string(name)
```


## Role System Implementation

### Role Enum
```python
class Role(models.TextChoices):
    GAMEMASTER = 'gamemaster', 'Gamemaster'
    PLAYER = 'player', 'Player'
    COUNTER = 'counter', 'Counter'
    SPECTATOR = 'spectator', 'Spectator'
```

### Permission Checking
```python
def check_permission(player, action):
    """Check if player has permission for action"""
    permissions = {
        Role.GAMEMASTER: ['mark_square', 'generate_board', 'reveal_fog', 
                         'assign_roles', 'remove_players'],
        Role.PLAYER: ['mark_square'],
        Role.COUNTER: ['review_claims'],
        Role.SPECTATOR: [],
    }
    
    # Gamemaster can only mark if they're also a player
    if action == 'mark_square' and player.role == Role.GAMEMASTER:
        return player.is_also_player  # New field or check
    
    return action in permissions.get(player.role, [])
```

### Gamemaster Assignment
```python
# Room creation
def create_room(user, room_name, is_gamemaster_only=False):
    room = Room.objects.create(name=room_name, creator=user)
    
    if is_gamemaster_only:
        role = Role.GAMEMASTER
        is_also_player = False
    else:
        role = Role.GAMEMASTER  # Can also mark squares
        is_also_player = True
    
    player = Player.objects.create(
        user=user,
        room=room,
        role=role,
        is_also_player=is_also_player
    )
    return room
```


## Counter/Claim Review System

### Claim State Machine

```
┌──────────┐
│   none   │ (Initial state)
└────┬─────┘
     │ Player marks square
     ▼
┌──────────────┐
│ under_review │ (Waiting for counter)
└──┬────────┬──┘
   │        │
   │        │ Counter rejects
   │        ▼
   │    ┌──────────┐
   │    │ rejected │ (Square unmarked)
   │    └──────────┘
   │
   │ Counter confirms
   ▼
┌───────────┐
│ confirmed │ (Square marked permanently)
└───────────┘
```

### Implementation

```python
def mark_square(player, slot, color):
    """Player marks a square"""
    square = Square.objects.get(game=player.room.current_game, slot=slot)
    
    # Check if player has a counter assigned
    counter = player.counters.first()
    
    if counter:
        # Claim goes under review
        square.claim_status = 'under_review'
        square.claimed_by = player
        square.colors.append(color)
        square.save()
        
        # Notify counter via WebSocket
        notify_counter(counter, player, slot, color)
    else:
        # No counter, mark immediately
        square.claim_status = 'confirmed'
        square.colors.append(color)
        square.save()
    
    # Create event
    GoalEvent.objects.create(
        player=player,
        slot=slot,
        claim_status=square.claim_status
    )

def review_claim(counter, slot, action):
    """Counter reviews a claim"""
    # Verify counter is assigned to the player who made the claim
    square = Square.objects.get(slot=slot)
    
    if square.claimed_by.counters.filter(id=counter.id).exists():
        if action == 'confirm':
            square.claim_status = 'confirmed'
        elif action == 'reject':
            square.claim_status = 'rejected'
            square.colors.remove(square.claimed_by.color)
            square.claimed_by = None
        
        square.reviewed_by = counter
        square.save()
        
        # Create review event
        ClaimReviewEvent.objects.create(
            player=counter,
            slot=slot,
            action=action,
            reviewed_player=square.claimed_by
        )
```


## Fog of War Implementation

### Client-Side Logic (board.js)

```javascript
class Board {
    constructor(fogOfWar) {
        this.fogOfWar = fogOfWar;
        this.squares = [];
    }
    
    hideSquares() {
        if (!this.fogOfWar) return;
        
        const chosenColor = this.colorChooser.getChosenColor();
        
        for (let i = 0; i < this.squares.length; i++) {
            // Hide all squares by default
            this.squares[i].hidden = true;
            
            // Reveal if square matches player's chosen color
            if (this.checkTile(i, chosenColor)) {
                this.squares[i].hidden = false;
            }
        }
        
        this.renderSquares();
    }
    
    checkTile(slot, color) {
        const square = this.squares[slot];
        
        // Check if square has the player's color
        if (square.colors.includes(color)) {
            return true;
        }
        
        // Check adjacent tiles (row, column, diagonal)
        const adjacentSlots = this.getAdjacentSlots(slot);
        for (const adjSlot of adjacentSlots) {
            if (this.squares[adjSlot].colors.includes(color)) {
                return true;
            }
        }
        
        return false;
    }
    
    getAdjacentSlots(slot) {
        // Returns slots in same row, column, and diagonals
        const row = Math.floor(slot / this.size);
        const col = slot % this.size;
        const adjacent = [];
        
        // Same row
        for (let c = 0; c < this.size; c++) {
            adjacent.push(row * this.size + c);
        }
        
        // Same column
        for (let r = 0; r < this.size; r++) {
            adjacent.push(r * this.size + col);
        }
        
        // Diagonals (TL-BR and TR-BL)
        // ... diagonal logic
        
        return adjacent;
    }
}
```


## User Statistics & Achievements

### Statistics Tracking

```python
def update_user_statistics(user, event_type, **kwargs):
    """Update user statistics based on events"""
    if event_type == 'game_completed':
        user.total_games_played += 1
    elif event_type == 'square_marked':
        user.total_squares_marked += 1
    elif event_type == 'bingo_completed':
        user.total_bingos_completed += 1
    elif event_type == 'game_won':
        user.wins += 1
    elif event_type == 'game_lost':
        user.losses += 1
    
    user.save()
    
    # Check for achievement unlocks
    check_achievements(user)
```

### Achievement System

```python
# Achievement definitions (loaded from fixtures or database)
ACHIEVEMENTS = [
    {
        'code': 'first_game',
        'name': 'First Steps',
        'description': 'Complete your first game',
        'category': 'milestone',
        'criteria': {'total_games_played': 1}
    },
    {
        'code': 'veteran',
        'name': 'Veteran Player',
        'description': 'Complete 100 games',
        'category': 'milestone',
        'criteria': {'total_games_played': 100}
    },
    {
        'code': 'row_bingo',
        'name': 'Row Master',
        'description': 'Complete a row bingo',
        'category': 'pattern',
        'criteria': {'pattern': 'row'}
    },
    {
        'code': 'speed_demon',
        'name': 'Speed Demon',
        'description': 'Complete a bingo in under 10 minutes',
        'category': 'speed',
        'criteria': {'completion_time': 600}  # seconds
    },
]

def check_achievements(user):
    """Check and award achievements"""
    for achievement_def in Achievement.objects.all():
        # Skip if already earned
        if UserAchievement.objects.filter(user=user, achievement=achievement_def).exists():
            continue
        
        # Check criteria
        if evaluate_criteria(user, achievement_def.criteria):
            # Award achievement
            user_achievement = UserAchievement.objects.create(
                user=user,
                achievement=achievement_def
            )
            
            # Broadcast to room if user is in one
            if user.current_room:
                broadcast_achievement(user.current_room, user, achievement_def)
```


## Deployment Architecture

### Docker Compose Setup

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: bingosync
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  django:
    build:
      context: ./bingosync-app
      dockerfile: Dockerfile
    command: gunicorn bingosync.wsgi:application --bind 0.0.0.0:8000 --workers 4
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/bingosync
      REDIS_URL: redis://redis:6379/0
      INTERNAL_API_SECRET: ${INTERNAL_API_SECRET}
      SECRET_KEY: ${DJANGO_SECRET_KEY}
      ALLOWED_HOSTS: ${ALLOWED_HOSTS}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - static_files:/app/static
      - media_files:/app/media

  tornado:
    build:
      context: ./bingosync-websocket
      dockerfile: Dockerfile
    command: python app.py
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASSWORD}@postgres:5432/bingosync
      REDIS_URL: redis://redis:6379/0
      INTERNAL_API_SECRET: ${INTERNAL_API_SECRET}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  nginx:
    image: nginx:1.24-alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - static_files:/static:ro
      - media_files:/media:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - django
      - tornado

volumes:
  postgres_data:
  redis_data:
  static_files:
  media_files:
```


### Nginx Configuration

```nginx
upstream django_app {
    server django:8000;
}

upstream tornado_ws {
    server tornado:8888;
}

server {
    listen 80;
    server_name _;
    
    # Redirect to HTTPS in production
    # return 301 https://$host$request_uri;
    
    # Static files
    location /static/ {
        alias /static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /media/;
        expires 7d;
    }
    
    # WebSocket
    location /websocket/ {
        proxy_pass http://tornado_ws;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 86400;
    }
    
    # Django application
    location / {
        proxy_pass http://django_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Security headers
        add_header X-Frame-Options "DENY" always;
        add_header X-Content-Type-Options "nosniff" always;
        add_header X-XSS-Protection "1; mode=block" always;
    }
}
```


## Performance Optimization Strategy

### Database Optimization

```python
# Query optimization examples

# Bad: N+1 query
for player in room.players.all():
    print(player.user.username)  # Hits DB for each player

# Good: Use select_related
players = room.players.select_related('user').all()

# Bad: N+1 for reverse relations
for room in Room.objects.all():
    print(room.players.count())  # Hits DB for each room

# Good: Use prefetch_related
rooms = Room.objects.prefetch_related('players').all()

# Indexes (already in models above)
class Meta:
    indexes = [
        Index(fields=['timestamp']),  # Event queries
        Index(fields=['room', 'user']),  # Player lookups
        Index(fields=['active']),  # Active room filtering
    ]
```

### Redis Caching

```python
from django.core.cache import cache

def get_room_settings(room_uuid):
    """Cache room settings"""
    cache_key = f'room_settings:{room_uuid}'
    settings = cache.get(cache_key)
    
    if settings is None:
        room = Room.objects.get(uuid=room_uuid)
        settings = room.get_settings()
        cache.set(cache_key, settings, timeout=300)  # 5 minutes
    
    return settings

def get_board_by_seed(seed):
    """Cache generated boards"""
    cache_key = f'board:{seed}'
    board = cache.get(cache_key)
    
    if board is None:
        board = generate_hp_cos_board(seed)
        cache.set(cache_key, board, timeout=86400)  # 24 hours
    
    return board

def invalidate_room_cache(room_uuid):
    """Invalidate cache when room changes"""
    cache.delete(f'room_settings:{room_uuid}')
```


### Node.js Process Pool for Generator

```python
# Generator execution with process pool
import subprocess
import json
from concurrent.futures import ProcessPoolExecutor

# Initialize pool at startup
generator_pool = ProcessPoolExecutor(max_workers=4)

def generate_board_async(seed):
    """Generate board using Node.js process pool"""
    future = generator_pool.submit(_run_generator, seed)
    return future.result(timeout=10)

def _run_generator(seed):
    """Run generator in subprocess"""
    result = subprocess.run(
        ['node', 'generators/hp_cos_generator.js', str(seed)],
        capture_output=True,
        text=True,
        timeout=10,
        cwd='/app/bingosync-app'
    )
    
    if result.returncode != 0:
        raise GeneratorException(result.stderr)
    
    return json.loads(result.stdout)
```

## HP Chamber of Secrets Generator Details

### Generator Structure

The HP CoS generator follows the standard Bingosync generator pattern:

1. **Seedrandom**: Uses Math.seedrandom() for reproducible randomization
2. **Difficulty Calculation**: Each board position (1-25) has a calculated difficulty tier
3. **Goal Selection**: Selects goals from the appropriate difficulty tier using Box-Muller distribution
4. **Synergy Checking**: Prevents similar goals on the same row/column/diagonal

### Goal List Structure

The goal list contains 25 difficulty tiers with multiple goals per tier:

```javascript
{
    "normal": {
        "1": [/* Easy goals */],
        "2": [/* Slightly harder */],
        // ... tiers 3-24
        "25": [/* Hardest goals */]
    },
    "lockout": [/* Special lockout mode goals */]
}
```

### Goal Properties

Each goal includes:
- `id`: Unique identifier
- `name`: Display name (may include variable amounts like "{3-4} frogs")
- `difficulty`: Tier number (1-25)
- `amount`: Base amount for the goal
- `types`: Synergy types (e.g., `{"castle": 1, "selfsynergy": 0}`)
- `triggers`: Array of goal IDs that this goal enables/conflicts with
- `rowtypes`: Metadata for card/bean/star counts

### Variable Amounts

Goals can have variable amounts using special syntax:
- `{min-max}`: Random number between min and max (e.g., "{3-4} chocolate frogs")
- `{opt1,opt2,opt3}`: Random choice from comma-separated options

### Synergy System

The synergy system prevents similar goals from appearing on the same line:
- Goals have `types` like "castle", "skurge", "diffindo", "multi", etc.
- When placing a goal, the generator checks all goals on intersecting lines
- Goals with matching types increase synergy score
- The generator selects the goal with lowest synergy

### Integration with Bingosync

The generator is already compatible with Bingosync's architecture:
1. Exports `bingoGenerator` function
2. Takes `bingoList` and `opts` (seed, mode, lang)
3. Returns array of 25 goal objects with `name`, `types`, `id`, `synergy`
4. Supports "normal" and "lockout" modes

## Monitoring & Observability

### Sentry Integration

```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

sentry_sdk.init(
    dsn=env('SENTRY_DSN'),
    integrations=[DjangoIntegration()],
    traces_sample_rate=0.1,
    send_default_pii=False,
    environment=env('ENVIRONMENT', default='development'),
)
```

### Structured Logging

```python
import logging
import structlog

# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info("user_login", username=user.username, ip=request.META['REMOTE_ADDR'])
logger.warning("rate_limit_exceeded", ip=request.META['REMOTE_ADDR'])
logger.error("generator_failed", seed=seed, error=str(e))
```


### Health Check Endpoints

```python
# views.py
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    """Health check for load balancers"""
    try:
        # Check database
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        # Check Redis
        from django.core.cache import cache
        cache.set('health_check', 'ok', 10)
        cache.get('health_check')
        
        return JsonResponse({
            'status': 'healthy',
            'database': 'ok',
            'cache': 'ok'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=503)
```

### Prometheus Metrics

```python
# Using django-prometheus
INSTALLED_APPS = [
    'django_prometheus',
    # ... other apps
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    # ... other middleware
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

# Exposes metrics at /metrics endpoint
# - django_http_requests_total
# - django_http_requests_latency_seconds
# - django_db_query_duration_seconds
```

## Migration Strategy

### Consolidating Migrations

```bash
# Step 1: Remove all existing migrations
rm bingosync-app/bingosync/migrations/0*.py

# Step 2: Create fresh initial migration
python manage.py makemigrations --name initial

# Step 3: Verify migration includes all models
python manage.py sqlmigrate bingosync 0001

# Step 4: Apply to fresh database
python manage.py migrate
```

### Initial Data Fixtures

```python
# fixtures/achievements.json
[
    {
        "model": "bingosync.achievement",
        "pk": 1,
        "fields": {
            "code": "first_game",
            "name": "First Steps",
            "description": "Complete your first game",
            "category": "milestone",
            "criteria": {"total_games_played": 1}
        }
    },
    // ... more achievements
]

# Load fixtures after migration
python manage.py loaddata achievements
```


## Frontend Architecture

### Bootstrap 5 Migration

```html
<!-- Old Bootstrap 3 -->
<div class="panel panel-default">
    <div class="panel-heading">Title</div>
    <div class="panel-body">Content</div>
</div>

<!-- New Bootstrap 5 -->
<div class="card">
    <div class="card-header">Title</div>
    <div class="card-body">Content</div>
</div>
```

### JavaScript Module Structure

```
static/bingosync/
├── room/
│   ├── board.js          # Board rendering and fog of war
│   ├── chat.js           # Chat functionality
│   ├── players.js        # Player list and role management
│   ├── counter.js        # Counter claim review UI
│   └── websocket.js      # WebSocket connection handling
├── auth/
│   ├── login.js          # Login form handling
│   └── register.js       # Registration form handling
└── profile/
    ├── statistics.js     # User statistics display
    └── achievements.js   # Achievement display
```

### Build Process (Webpack)

```javascript
// webpack.config.js
module.exports = {
    entry: {
        room: './static/bingosync/room/index.js',
        auth: './static/bingosync/auth/index.js',
        profile: './static/bingosync/profile/index.js',
    },
    output: {
        path: path.resolve(__dirname, 'static/dist'),
        filename: '[name].[contenthash].js',
    },
    optimization: {
        minimize: true,
        splitChunks: {
            chunks: 'all',
        },
    },
};
```


## Testing Strategy

### Test Structure

```
bingosync-app/tests/
├── unit/
│   ├── test_models.py          # Model tests
│   ├── test_forms.py           # Form validation tests
│   ├── test_generators.py      # Generator tests
│   └── test_achievements.py    # Achievement logic tests
├── integration/
│   ├── test_room_flow.py       # Room creation to gameplay
│   ├── test_auth_flow.py       # Registration to login
│   ├── test_counter_flow.py    # Claim review workflow
│   └── test_fog_of_war.py      # Fog of war functionality
└── e2e/
    └── test_full_game.py       # Complete game scenarios
```

### Example Tests

```python
# tests/unit/test_models.py
class UserModelTest(TestCase):
    def test_user_can_only_join_one_room(self):
        user = User.objects.create_user('testuser', 'test@example.com', 'password')
        room1 = Room.objects.create(name='Room 1', creator=user)
        room2 = Room.objects.create(name='Room 2', creator=user)
        
        user.current_room = room1
        user.save()
        
        # Attempting to join room2 should fail
        with self.assertRaises(ValidationError):
            user.current_room = room2
            user.full_clean()

# tests/integration/test_counter_flow.py
class CounterFlowTest(TestCase):
    def test_claim_review_workflow(self):
        # Setup: Create room with player and counter
        gm = User.objects.create_user('gm', 'gm@example.com', 'password')
        player = User.objects.create_user('player', 'player@example.com', 'password')
        counter = User.objects.create_user('counter', 'counter@example.com', 'password')
        
        room = Room.objects.create(name='Test Room', creator=gm)
        player_obj = Player.objects.create(user=player, room=room, role=Role.PLAYER)
        counter_obj = Player.objects.create(user=counter, room=room, role=Role.COUNTER)
        counter_obj.monitoring_player = player_obj
        counter_obj.save()
        
        # Player marks square
        response = self.client.post(f'/api/rooms/{room.uuid}/select', {
            'slot': 12,
            'color': 'red'
        })
        
        # Verify claim is under review
        square = Square.objects.get(game=room.current_game, slot=12)
        self.assertEqual(square.claim_status, 'under_review')
        
        # Counter confirms claim
        self.client.login(username='counter', password='password')
        response = self.client.post(f'/api/rooms/{room.uuid}/review-claim', {
            'slot': 12,
            'action': 'confirm'
        })
        
        # Verify claim is confirmed
        square.refresh_from_db()
        self.assertEqual(square.claim_status, 'confirmed')
```


## Implementation Phases

### Phase 1: Foundation & Security (Weeks 1-4)
**Priority: P0 Security + P2 Code Quality**

1. Database migration consolidation (Req 7)
2. PostgreSQL-only support (Req 8)
3. Security vulnerability remediation (Req 11)
   - Rate limiting
   - CSRF protection
   - Secure cookies
   - Django-Tornado authentication
4. Remove NixOS deployment (Req 10)
5. Game generator simplification (Req 1)
   - Remove 360+ generators
   - Keep HP CoS generator structure

**Deliverables:**
- Fresh 0001_initial.py migration
- PostgreSQL-only configuration
- Security headers and rate limiting
- Shared secret authentication
- Single HP CoS generator

### Phase 2: Core Features (Weeks 5-8)
**Priority: Feature Requirements**

1. Persistent user accounts (Req 3)
   - User model with statistics fields
   - Registration/login/logout
   - Password reset
   - One room at a time enforcement
2. Role-based access control (Req 4)
   - Role enum and permissions
   - Gamemaster assignment options
   - Role change functionality
3. Docker Compose deployment (Req 9)
   - docker-compose.yml
   - Dockerfiles for Django and Tornado
   - Nginx configuration
   - Environment variable setup

**Deliverables:**
- Working user authentication
- Role system with permissions
- Docker Compose deployment
- User can create/join rooms with roles


### Phase 3: Advanced Features (Weeks 9-12)
**Priority: Feature Requirements**

1. Fog of war integration (Req 5)
   - Merge feature/fog-of-war branch
   - Test fog of war with new role system
   - Update UI for fog status
2. Counter role and claim review (Req 6)
   - Counter assignment to players
   - Claim state machine (under_review → confirmed/rejected)
   - Counter UI for reviewing claims
   - WebSocket events for claim reviews
3. Performance optimization (Req 12)
   - Database indexes
   - Redis caching
   - Query optimization (select_related, prefetch_related)
   - Board caching by seed

**Deliverables:**
- Fog of war working with roles
- Counter claim review system
- Performance improvements
- Redis caching layer

### Phase 4: Statistics & Quality (Weeks 13-16)
**Priority: P2 Code Quality + P4 Testing**

1. User statistics and achievements (Req 18)
   - Statistics tracking
   - Achievement definitions
   - Achievement checking and awarding
   - Profile page with stats and achievements
2. Comprehensive testing (Req 14)
   - Unit tests for models, forms, views
   - Integration tests for workflows
   - WebSocket tests
   - Achieve 60% coverage
3. Code quality improvements (Req 13)
   - Remove commented code and TODOs
   - Add type hints
   - Split views.py into modules
   - Linting with ruff
   - Add docstrings

**Deliverables:**
- User statistics and achievements
- 60%+ test coverage
- Clean, well-documented code
- Zero linting errors


### Phase 5: Polish & Production (Weeks 17-20)
**Priority: P3 Documentation + Frontend**

1. Frontend modernization (Req 17)
   - Bootstrap 3 → 5 migration
   - Webpack bundling
   - Responsive design
   - Accessibility improvements
2. Dependency updates (Req 16)
   - Django 4.2 LTS
   - Tornado latest
   - Bootstrap 5
   - Remove six, pytz
   - Security updates
3. Documentation (Req 15)
   - README with installation instructions
   - API documentation
   - WebSocket protocol docs
   - Architecture diagrams
   - CONTRIBUTING.md
4. Monitoring and observability (Req 19)
   - Sentry integration
   - Structured logging
   - Health check endpoints
   - Prometheus metrics
5. Project branding (Req 20)
   - Update README description
   - Update page titles for HP CoS focus

**Deliverables:**
- Modern, responsive UI
- Up-to-date dependencies
- Comprehensive documentation
- Production monitoring
- Production-ready platform

## Success Metrics

### Performance Targets
- Average response time < 200ms
- Board generation < 2s (dev) / 10s (prod)
- WebSocket latency < 100ms
- Database query count < 10 per request

### Quality Targets
- Test coverage ≥ 60%
- Zero linting errors
- Zero critical security vulnerabilities
- All dependencies up-to-date

### Feature Completeness
- ✅ Single HP CoS generator
- ✅ User accounts with statistics
- ✅ Role-based access control
- ✅ Counter claim review system
- ✅ Fog of war
- ✅ Achievement system
- ✅ Docker Compose deployment
- ✅ Production monitoring

## Conclusion

This design provides a comprehensive technical blueprint for transforming Bingosync into a specialized HP Chamber of Secrets bingo platform. The phased approach prioritizes security and core functionality first, followed by advanced features, quality improvements, and production readiness. The architecture leverages modern best practices while maintaining the existing Django + Tornado stack, ensuring a smooth transition from the current codebase.
