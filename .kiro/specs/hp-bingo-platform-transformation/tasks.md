# Tasks: HP Bingo Platform Transformation

## Task Status Legend
- `[ ]` - Not started
- `[-]` - In progress
- `[x]` - Completed
- `[~]` - Queued

---

## Phase 1: Foundation & Security (Weeks 1-4)

- [x] 1.1 Database Migration Consolidation
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Remove all 41 existing Django migration files and create a single fresh 0001_initial.py migration with the complete schema for all models.

**Acceptance Criteria:**
- All existing migration files (0001-0041) are deleted
- New 0001_initial.py migration created with complete schema
- Migration applies successfully to empty PostgreSQL database
- All models (User, Room, Game, Player, Square, Events, Achievement, UserAchievement) included

**Files to Modify:**
- `bingosync-app/bingosync/migrations/` (delete all, create 0001_initial.py)

---

- [x] 1.2 PostgreSQL-Only Database Support
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 3 hours
  **Dependencies:** Task 1.1

  **Description:**
Remove SQLite support and configure the platform to use only PostgreSQL.

**Acceptance Criteria:**
- SQLite database backend removed from settings.py
- DATABASE_URL environment variable required
- Descriptive error if DATABASE_URL not set
- SQLite database file removed from repository
- PostgreSQL version requirements documented in README

**Files to Modify:**
- `bingosync-app/bingosync/settings.py`
- `bingosync-app/db.sqlite3` (delete)
- `README.md`

---


- [x] 1.3 Implement Rate Limiting
  **Priority:** P0 (Security)
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Add rate limiting to all public HTTP endpoints using django-ratelimit.

**Acceptance Criteria:**
- django-ratelimit added to requirements.txt
- Rate limiting applied to login (10/min per IP)
- Rate limiting applied to registration (5/min per IP)
- Rate limiting applied to authenticated actions (100/hour per user)
- Rate limiting applied to WebSocket connections (20/min per IP)
- 429 Too Many Requests returned when limit exceeded

**Files to Modify:**
- `requirements.txt`
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/decorators.py` (create)
- `bingosync-websocket/app.py`

---

- [x] 1.4 Enable CSRF Protection
  **Priority:** P0 (Security)
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Enable CSRF protection on all state-changing API endpoints.

**Acceptance Criteria:**
- CSRF middleware enabled in settings.py
- CSRF tokens included in all forms
- CSRF validation on POST/PUT/DELETE endpoints
- CSRF_COOKIE_SECURE = True in production
- API endpoints return 403 Forbidden without valid CSRF token

**Files to Modify:**
- `bingosync-app/bingosync/settings.py`
- `bingosync-app/templates/bingosync/*.html`

---

- [x] 1.5 Configure Secure Cookies
  **Priority:** P0 (Security)
  **Estimated Time:** 2 hours
  **Dependencies:** None

  **Description:**
Set secure cookie flags for production environment.

**Acceptance Criteria:**
- SESSION_COOKIE_SECURE = True in production
- SESSION_COOKIE_HTTPONLY = True
- SESSION_COOKIE_SAMESITE = 'Lax'
- CSRF_COOKIE_SECURE = True in production
- CSRF_COOKIE_HTTPONLY = True

**Files to Modify:**
- `bingosync-app/bingosync/settings.py`

---


- [x] 1.6 Implement Django-Tornado Shared Secret Authentication
  **Priority:** P0 (Security)
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Implement shared secret authentication between Django and Tornado servers for internal API calls.

**Acceptance Criteria:**
- INTERNAL_API_SECRET environment variable required
- Django sends X-Internal-Secret header to Tornado
- Tornado validates header on internal endpoints
- 401 Unauthorized returned for invalid/missing secret
- Secret is 32+ characters random string

**Files to Modify:**
- `bingosync-app/bingosync/settings.py`
- `bingosync-app/bingosync/util.py`
- `bingosync-websocket/app.py`
- `.env.example` (create)

---

- [x] 1.7 Add Security Headers
  **Priority:** P0 (Security)
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Add security headers to all HTTP responses.

**Acceptance Criteria:**
- SECURE_SSL_REDIRECT = True in production
- SECURE_HSTS_SECONDS = 31536000
- SECURE_CONTENT_TYPE_NOSNIFF = True
- X_FRAME_OPTIONS = 'DENY'
- CSP headers configured
- Security headers present in all responses

**Files to Modify:**
- `bingosync-app/bingosync/settings.py`
- `bingosync-app/bingosync/middleware.py` (create if needed)

---

- [x] 1.8 Validate WebSocket Origins
  **Priority:** P0 (Security)
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Validate WebSocket connection origins against allowed domains.

**Acceptance Criteria:**
- Origin header validated on WebSocket connections
- ALLOWED_HOSTS used for validation
- Connections from unauthorized origins rejected
- Error logged for rejected connections

**Files to Modify:**
- `bingosync-websocket/app.py`

---


- [ ] 1.9 Input Validation and Sanitization
  **Priority:** P0 (Security)
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Validate and sanitize all user inputs through Django forms.

**Acceptance Criteria:**
- All user inputs validated through Django forms
- Profanity filter applied to room names and usernames
- SQL injection prevention (Django ORM handles this)
- XSS prevention through template escaping
- Max length validation on all text fields

**Files to Modify:**
- `bingosync-app/bingosync/forms.py`
- `bingosync-app/bingosync/validators.py` (create)

---

- [ ] 1.10 Remove NixOS Deployment Configuration
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 1 hour
  **Dependencies:** None

  **Description:**
Remove NixOS-specific deployment configuration files.

**Acceptance Criteria:**
- flake.nix file deleted
- All NixOS-specific files removed
- NixOS documentation removed from README
- README updated to reference Docker Compose

**Files to Modify:**
- `flake.nix` (delete)
- `README.md`

---

- [ ] 1.11 Game Generator Simplification - Remove Generators
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Remove all 360+ existing game generator files except HP Chamber of Secrets.

**Acceptance Criteria:**
- All generator files deleted except hp_cos_generator.js
- All generator JSON files deleted except hp_cos goal-list.js
- Generator base classes not used by HP CoS removed
- Test data for other generators removed
- seedrandom library retained (used by HP CoS generator)

**Files to Modify:**
- `bingosync-app/generators/` (delete most files)
- `bingosync-app/generators/generator_jsons/` (delete most files)
- `bingosync-app/generators/generator_bases/` (keep only what HP CoS needs)

---

- [ ] 1.12 Integrate HP CoS Generator Files
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 4 hours
  **Dependencies:** Task 1.11

  **Description:**
Copy the HP CoS generator and goal list from temp directory to the generators directory and ensure they work with Bingosync's infrastructure.

**Acceptance Criteria:**
- generator.js copied to `bingosync-app/generators/hp_cos_generator.js`
- goal-list.js copied to `bingosync-app/generators/hp_cos_goal_list.js`
- Generator exports bingoGenerator function correctly
- Goal list exports bingoList object correctly
- Generator can be invoked from Python via subprocess
- Test generation with multiple seeds works
- Variable amounts ({min-max} syntax) work correctly
- Synergy system prevents similar goals on same line

**Files to Modify:**
- `bingosync-app/generators/hp_cos_generator.js` (create from temp)
- `bingosync-app/generators/hp_cos_goal_list.js` (create from temp)
- `bingosync-app/bingosync/generators.py` (update to use HP CoS generator)

---

- [ ] 1.13 Test HP CoS Generator Integration
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 3 hours
  **Dependencies:** Task 1.12

  **Description:**
Test the HP CoS generator thoroughly to ensure it works correctly with Bingosync.

**Acceptance Criteria:**
- Generator produces valid 25-goal boards
- Same seed produces same board (reproducibility)
- All 25 difficulty tiers represented across multiple boards
- Variable amounts randomize correctly
- Synergy system works (no duplicate goal types on lines)
- Lockout mode goals work (if implemented)
- Board generation completes within 2 seconds
- No JavaScript errors in generator execution

**Files to Modify:**
- `bingosync-app/tests/test_hp_cos_generator.py` (create)

---

- [ ] 1.14 Game Generator Simplification - Update Models
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 3 hours
  **Dependencies:** Task 1.13

  **Description:**
Remove game type selection and simplify to HP CoS only.

**Acceptance Criteria:**
- game_type.py simplified to single HP CoS entry
- Room creation form removes game type selection
- Rooms automatically use HP CoS generator
- Game model no longer needs game_type_value field (or defaults to HP CoS)

**Files to Modify:**
- `bingosync-app/bingosync/models/game_type.py`
- `bingosync-app/bingosync/forms.py`
- `bingosync-app/bingosync/models/rooms.py`

---

## Phase 2: Core Features (Weeks 5-8)

- [ ] 2.1 Create User Model with Statistics
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** Task 1.1

  **Description:**
Extend Django's User model with statistics fields for tracking gameplay.

**Acceptance Criteria:**
- User model extends AbstractUser
- Fields: current_room, total_games_played, total_squares_marked, total_bingos_completed, wins, losses
- current_room enforces one room at a time
- Statistics fields default to 0
- Migration created for User model

**Files to Modify:**
- `bingosync-app/bingosync/models/user.py` (create)
- `bingosync-app/bingosync/models/__init__.py`

---

- [ ] 2.2 Implement User Registration
  **Priority:** Feature
  **Estimated Time:** 5 hours
  **Dependencies:** Task 2.1

  **Description:**
Create user registration functionality with username, email, and password.

**Acceptance Criteria:**
- Registration form with username, email, password, password confirmation
- Email validation
- Unique username enforcement
- Password strength validation
- User created with hashed password (PBKDF2)
- Redirect to login after successful registration

**Files to Modify:**
- `bingosync-app/bingosync/forms.py`
- `bingosync-app/bingosync/views.py`
- `bingosync-app/templates/bingosync/register.html` (create)
- `bingosync-app/bingosync/urls.py`

---


- [ ] 2.3 Implement User Login/Logout
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** Task 2.2

  **Description:**
Create login and logout functionality using username and password.

**Acceptance Criteria:**
- Login form with username and password
- Session-based authentication
- Redirect to homepage after login
- Logout functionality clears session
- "Remember me" checkbox optional
- Failed login attempts logged

**Files to Modify:**
- `bingosync-app/bingosync/forms.py`
- `bingosync-app/bingosync/views.py`
- `bingosync-app/templates/bingosync/login.html` (create)
- `bingosync-app/bingosync/urls.py`

---

- [ ] 2.4 Implement Password Reset
  **Priority:** Feature
  **Estimated Time:** 5 hours
  **Dependencies:** Task 2.3

  **Description:**
Create password reset functionality via email.

**Acceptance Criteria:**
- Password reset request form (email input)
- Password reset email sent with token
- Password reset confirmation form
- Token expires after 24 hours
- Email configuration documented

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/templates/bingosync/password_reset*.html` (create multiple)
- `bingosync-app/bingosync/urls.py`
- `bingosync-app/bingosync/settings.py` (email config)

---

- [ ] 2.5 Enforce One Room Per User
  **Priority:** Feature
  **Estimated Time:** 3 hours
  **Dependencies:** Task 2.1

  **Description:**
Enforce that users can only be in one room at a time.

**Acceptance Criteria:**
- User.current_room field tracks active room
- Joining a room sets current_room
- Attempting to join second room shows error
- Leaving room clears current_room
- Validation in join_room view

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/models/user.py`

---


- [ ] 2.6 Create Role Enum and Model Fields
  **Priority:** Feature
  **Estimated Time:** 3 hours
  **Dependencies:** Task 1.1

  **Description:**
Add role system to Player model with four distinct roles.

**Acceptance Criteria:**
- Role enum with GAMEMASTER, PLAYER, COUNTER, SPECTATOR
- Player.role field added
- Player.is_also_player field for GM+Player combo
- Player.monitoring_player field for Counter assignments
- Migration created

**Files to Modify:**
- `bingosync-app/bingosync/models/rooms.py`
- `bingosync-app/bingosync/models/enums.py` (create)

---

- [ ] 2.7 Implement Role-Based Permissions
  **Priority:** Feature
  **Estimated Time:** 5 hours
  **Dependencies:** Task 2.6

  **Description:**
Implement permission checking for role-based actions.

**Acceptance Criteria:**
- check_permission() function created
- Permissions defined for each role
- Gamemaster can mark squares only if is_also_player
- Players can mark squares
- Counters can review claims
- Spectators can only view
- Permission checks in all action views

**Files to Modify:**
- `bingosync-app/bingosync/permissions.py` (create)
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/decorators.py`

---

- [ ] 2.8 Implement Gamemaster Assignment Options
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** Task 2.7

  **Description:**
Allow room creator to choose GM-only or GM+Player role.

**Acceptance Criteria:**
- Room creation form has "Gamemaster only" checkbox
- If checked, creator is GM-only (cannot mark squares)
- If unchecked, creator is GM+Player (can mark squares)
- is_also_player field set correctly
- UI shows role clearly

**Files to Modify:**
- `bingosync-app/bingosync/forms.py`
- `bingosync-app/bingosync/views.py`
- `bingosync-app/templates/bingosync/index.html`

---


- [ ] 2.9 Implement Role Change Functionality
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** Task 2.7

  **Description:**
Allow Gamemaster to change participant roles.

**Acceptance Criteria:**
- assign_role endpoint created
- Only Gamemaster can change roles
- RoleChangeEvent created on change
- WebSocket broadcast of role change
- UI for role management in players panel

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/models/events.py`
- `bingosync-app/static/bingosync/room/players.js`
- `bingosync-app/templates/bingosync/players_panel.html`

---

- [x] 2.10 Create Docker Compose Configuration
  **Priority:** Feature
  **Estimated Time:** 6 hours
  **Dependencies:** Task 1.2

  **Description:**
Create docker-compose.yml with all services.

**Acceptance Criteria:**
- docker-compose.yml with postgres, redis, django, tornado, nginx services
- Health checks for postgres and redis
- Docker volumes for data persistence
- Docker networks for service communication
- .env.example file with all required variables
- Services start successfully with docker-compose up

**Files to Modify:**
- `docker-compose.yml` (create)
- `.env.example` (create)
- `.dockerignore` (create)

---

- [x] 2.11 Create Django Dockerfile
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** Task 2.10

  **Description:**
Create Dockerfile for Django application.

**Acceptance Criteria:**
- Multi-stage build for smaller image
- Python 3.11+ base image
- Requirements installed
- Static files collected
- Gunicorn as WSGI server
- Non-root user
- Health check endpoint

**Files to Modify:**
- `bingosync-app/Dockerfile` (create)
- `bingosync-app/.dockerignore` (create)

---


- [x] 2.12 Create Tornado Dockerfile
  **Priority:** Feature
  **Estimated Time:** 3 hours
  **Dependencies:** Task 2.10

  **Description:**
Create Dockerfile for Tornado WebSocket server.

**Acceptance Criteria:**
- Python 3.11+ base image
- Requirements installed
- Non-root user
- Health check endpoint
- Tornado runs on port 8888

**Files to Modify:**
- `bingosync-websocket/Dockerfile` (create)
- `bingosync-websocket/.dockerignore` (create)

---

- [x] 2.13 Create Nginx Configuration
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** Task 2.10

  **Description:**
Create Nginx configuration for reverse proxy.

**Acceptance Criteria:**
- Nginx routes HTTP to Django
- Nginx routes WebSocket to Tornado
- Static files served by Nginx
- Security headers added
- HTTPS configuration (commented for dev)
- Gzip compression enabled

**Files to Modify:**
- `nginx.conf` (create)
- `docker-compose.yml`

---

## Phase 3: Advanced Features (Weeks 9-12)

- [ ] 3.1 Merge Fog of War Branch
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** Task 2.6

  **Description:**
Merge the feature/fog-of-war branch into main.

**Acceptance Criteria:**
- feature/fog-of-war branch merged
- Merge conflicts resolved
- fog_of_war field in Game model
- fog_of_war checkbox in RoomForm
- Board.js hideSquares() and checkTile() methods present
- Tests pass after merge

**Files to Modify:**
- Multiple files from merge

---


- [ ] 3.2 Test Fog of War with Role System
  **Priority:** Feature
  **Estimated Time:** 3 hours
  **Dependencies:** Task 3.1, Task 2.7

  **Description:**
Ensure fog of war works correctly with the new role system.

**Acceptance Criteria:**
- All roles see fog of war correctly
- Spectators see only revealed squares
- Gamemaster can reveal board (if implemented)
- fog_of_war status in WebSocket messages
- UI shows fog status clearly

**Files to Modify:**
- `bingosync-app/static/bingosync/room/board.js`
- `bingosync-websocket/app.py`

---

- [ ] 3.3 Create Square Model with Claim Status
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** Task 1.1

  **Description:**
Add claim_status field to Square model for claim review system.

**Acceptance Criteria:**
- Square model has claim_status field (none, under_review, confirmed, rejected)
- Square model has claimed_by and reviewed_by foreign keys
- Migration created
- Indexes on game and slot

**Files to Modify:**
- `bingosync-app/bingosync/models/rooms.py`

---

- [ ] 3.4 Implement Counter Assignment
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** Task 2.6, Task 3.3

  **Description:**
Allow Gamemaster to assign Counters to specific Players.

**Acceptance Criteria:**
- assign_counter endpoint created
- Only Gamemaster can assign counters
- Player.monitoring_player set correctly
- UI for counter assignment in players panel
- WebSocket broadcast of assignment

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/static/bingosync/room/players.js`
- `bingosync-app/templates/bingosync/players_panel.html`

---


- [ ] 3.5 Implement Claim Under Review Logic
  **Priority:** Feature
  **Estimated Time:** 5 hours
  **Dependencies:** Task 3.3, Task 3.4

  **Description:**
When a player with an assigned counter marks a square, place it under review.

**Acceptance Criteria:**
- mark_square checks if player has counter
- If counter exists, claim_status = 'under_review'
- If no counter, claim_status = 'confirmed'
- GoalEvent includes claim_status
- WebSocket message includes claim_status
- UI shows "under review" state

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/models/events.py`
- `bingosync-app/static/bingosync/room/board.js`
- `bingosync-websocket/app.py`

---

- [ ] 3.6 Implement Claim Review Endpoint
  **Priority:** Feature
  **Estimated Time:** 5 hours
  **Dependencies:** Task 3.5

  **Description:**
Create endpoint for Counters to confirm or reject claims.

**Acceptance Criteria:**
- review_claim endpoint created
- Only assigned Counter can review
- Confirm action sets claim_status = 'confirmed'
- Reject action sets claim_status = 'rejected' and removes color
- ClaimReviewEvent created
- WebSocket broadcast of review
- UI for counter to review claims

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/models/events.py`
- `bingosync-app/static/bingosync/room/counter.js` (create)
- `bingosync-app/templates/bingosync/counter_panel.html` (create)

---

- [ ] 3.7 Create Counter UI Panel
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** Task 3.6

  **Description:**
Create UI panel for Counters to review claims.

**Acceptance Criteria:**
- Counter panel shows pending claims for assigned player
- Confirm and Reject buttons
- Real-time updates via WebSocket
- Shows claim history
- Only visible to Counters

**Files to Modify:**
- `bingosync-app/templates/bingosync/bingosync.html`
- `bingosync-app/templates/bingosync/counter_panel.html` (create)
- `bingosync-app/static/bingosync/room/counter.js` (create)

---


- [ ] 3.8 Add Database Indexes
  **Priority:** P1 (Performance)
  **Estimated Time:** 2 hours
  **Dependencies:** Task 1.1

  **Description:**
Add database indexes for frequently queried fields.

**Acceptance Criteria:**
- Index on Event.timestamp
- Index on Player.room_id
- Index on Square.game_id
- Index on Room.active
- Composite index on Player(room, user)
- Migration created

**Files to Modify:**
- `bingosync-app/bingosync/models/rooms.py`
- `bingosync-app/bingosync/models/events.py`

---

- [ ] 3.9 Optimize Database Queries with select_related
  **Priority:** P1 (Performance)
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Use select_related() to prevent N+1 queries on foreign keys.

**Acceptance Criteria:**
- Player queries use select_related('user', 'room')
- Event queries use select_related('player')
- Square queries use select_related('game', 'claimed_by')
- Query count reduced in views
- Performance improvement measurable

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/models/rooms.py`

---

- [ ] 3.10 Optimize Database Queries with prefetch_related
  **Priority:** P1 (Performance)
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Use prefetch_related() to prevent N+1 queries on reverse relations.

**Acceptance Criteria:**
- Room queries use prefetch_related('players', 'games')
- Game queries use prefetch_related('squares')
- Query count reduced
- Performance improvement measurable

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/models/rooms.py`

---


- [ ] 3.11 Implement Redis Caching
  **Priority:** P1 (Performance)
  **Estimated Time:** 5 hours
  **Dependencies:** Task 2.10

  **Description:**
Add Redis caching for room settings and player lists.

**Acceptance Criteria:**
- Redis added to docker-compose.yml
- django-redis added to requirements.txt
- Cache backend configured in settings.py
- Room settings cached (5 min TTL)
- Player lists cached (1 min TTL)
- Cache invalidation on changes

**Files to Modify:**
- `docker-compose.yml`
- `requirements.txt`
- `bingosync-app/bingosync/settings.py`
- `bingosync-app/bingosync/cache.py` (create)
- `bingosync-app/bingosync/views.py`

---

- [ ] 3.12 Implement Board Caching by Seed
  **Priority:** P1 (Performance)
  **Estimated Time:** 3 hours
  **Dependencies:** Task 3.11

  **Description:**
Cache generated boards by seed value to avoid regeneration.

**Acceptance Criteria:**
- Generated boards cached by seed (24 hour TTL)
- Cache hit returns cached board
- Cache miss generates and caches board
- Cache key format: 'board:{seed}'
- Performance improvement measurable

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/cache.py`

---

## Phase 4: Statistics & Quality (Weeks 13-16)

- [ ] 4.1 Create Achievement Model
  **Priority:** Feature
  **Estimated Time:** 3 hours
  **Dependencies:** Task 1.1

  **Description:**
Create Achievement and UserAchievement models.

**Acceptance Criteria:**
- Achievement model with code, name, description, category, criteria
- UserAchievement model with user, achievement, earned_date, progress
- Unique constraint on (user, achievement)
- Migration created

**Files to Modify:**
- `bingosync-app/bingosync/models/achievements.py` (create)
- `bingosync-app/bingosync/models/__init__.py`

---


- [ ] 4.2 Define Achievement Fixtures
  **Priority:** Feature
  **Estimated Time:** 3 hours
  **Dependencies:** Task 4.1

  **Description:**
Create achievement definitions as fixtures.

**Acceptance Criteria:**
- Fixture file with 10+ achievements
- Milestone achievements (first game, 10 games, 100 games)
- Pattern achievements (row, column, diagonal, blackout)
- Speed achievements (fast bingo completion)
- Fixtures load successfully

**Files to Modify:**
- `bingosync-app/bingosync/fixtures/achievements.json` (create)

---

- [ ] 4.3 Implement Statistics Tracking
  **Priority:** Feature
  **Estimated Time:** 5 hours
  **Dependencies:** Task 2.1

  **Description:**
Track user statistics on game events.

**Acceptance Criteria:**
- update_user_statistics() function created
- total_games_played incremented on game completion
- total_squares_marked incremented on square mark
- total_bingos_completed incremented on bingo
- wins/losses incremented in lockout mode
- Statistics updated in real-time

**Files to Modify:**
- `bingosync-app/bingosync/statistics.py` (create)
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/signals.py` (create)

---

- [ ] 4.4 Implement Achievement Checking
  **Priority:** Feature
  **Estimated Time:** 6 hours
  **Dependencies:** Task 4.2, Task 4.3

  **Description:**
Check and award achievements when criteria are met.

**Acceptance Criteria:**
- check_achievements() function created
- Criteria evaluation for all achievement types
- UserAchievement created when earned
- Achievement unlocks broadcast via WebSocket
- Duplicate achievements prevented

**Files to Modify:**
- `bingosync-app/bingosync/achievements.py` (create)
- `bingosync-app/bingosync/statistics.py`
- `bingosync-websocket/app.py`

---


- [ ] 4.5 Create User Profile Page
  **Priority:** Feature
  **Estimated Time:** 5 hours
  **Dependencies:** Task 4.3, Task 4.4

  **Description:**
Create user profile page displaying statistics and achievements.

**Acceptance Criteria:**
- Profile page shows username, join date
- Statistics displayed (games played, squares marked, bingos, win/loss ratio)
- Earned achievements displayed with icons
- Achievement progress shown for incomplete achievements
- Room history displayed
- Accessible at /users/{username}

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/templates/bingosync/profile.html` (create)
- `bingosync-app/bingosync/urls.py`
- `bingosync-app/static/bingosync/profile/` (create directory)

---

- [ ] 4.6 Write Unit Tests for Models
  **Priority:** P4 (Testing)
  **Estimated Time:** 8 hours
  **Dependencies:** Task 1.1

  **Description:**
Write comprehensive unit tests for all models.

**Acceptance Criteria:**
- Tests for User model (one room enforcement, statistics)
- Tests for Room model
- Tests for Game model
- Tests for Player model (roles, counter assignment)
- Tests for Square model (claim status)
- Tests for Event models
- Tests for Achievement models
- All tests pass

**Files to Modify:**
- `bingosync-app/tests/unit/test_models.py` (create)

---

- [ ] 4.7 Write Unit Tests for Forms
  **Priority:** P4 (Testing)
  **Estimated Time:** 4 hours
  **Dependencies:** Task 2.2

  **Description:**
Write unit tests for all forms and validators.

**Acceptance Criteria:**
- Tests for registration form validation
- Tests for login form validation
- Tests for room creation form
- Tests for profanity filter
- Tests for input sanitization
- All tests pass

**Files to Modify:**
- `bingosync-app/tests/unit/test_forms.py` (create)

---


- [ ] 4.8 Write Unit Tests for Views
  **Priority:** P4 (Testing)
  **Estimated Time:** 10 hours
  **Dependencies:** Task 2.3

  **Description:**
Write unit tests for all views and API endpoints.

**Acceptance Criteria:**
- Tests for authentication views
- Tests for room CRUD operations
- Tests for game actions (mark square, new card)
- Tests for role management
- Tests for counter claim review
- Tests for permission enforcement
- All tests pass

**Files to Modify:**
- `bingosync-app/tests/unit/test_views.py` (create)

---

- [ ] 4.9 Write Integration Tests
  **Priority:** P4 (Testing)
  **Estimated Time:** 12 hours
  **Dependencies:** Task 4.8

  **Description:**
Write integration tests for complete user workflows.

**Acceptance Criteria:**
- Test: Registration → Login → Create Room → Play Game
- Test: Join Room → Mark Squares → Complete Bingo
- Test: Counter Assignment → Claim Review → Confirm/Reject
- Test: Fog of War → Reveal Squares
- Test: Achievement Unlock
- All tests pass

**Files to Modify:**
- `bingosync-app/tests/integration/test_flows.py` (create)

---

- [ ] 4.10 Write WebSocket Tests
  **Priority:** P4 (Testing)
  **Estimated Time:** 6 hours
  **Dependencies:** Task 4.8

  **Description:**
Write tests for WebSocket connection and message broadcasting.

**Acceptance Criteria:**
- Test WebSocket connection
- Test message broadcasting
- Test origin validation
- Test authentication
- All tests pass

**Files to Modify:**
- `bingosync-websocket/tests/test_websocket.py` (create)

---


- [ ] 4.11 Set Up CI Pipeline
  **Priority:** P4 (Testing)
  **Estimated Time:** 4 hours
  **Dependencies:** Task 4.9

  **Description:**
Set up continuous integration to run tests on pull requests.

**Acceptance Criteria:**
- GitHub Actions workflow created
- Tests run on all PRs
- Coverage report generated
- Minimum 60% coverage enforced
- Failed tests block merge

**Files to Modify:**
- `.github/workflows/ci.yml` (create)

---

- [ ] 4.12 Remove Commented Code
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Remove all commented-out code from the codebase.

**Acceptance Criteria:**
- All commented code removed
- Only explanatory comments remain
- Code still functions correctly

**Files to Modify:**
- Multiple files throughout codebase

---

- [ ] 4.13 Convert TODOs to GitHub Issues
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 2 hours
  **Dependencies:** None

  **Description:**
Convert all TODO comments to GitHub issues and remove from code.

**Acceptance Criteria:**
- All TODOs identified
- GitHub issues created for each
- TODO comments removed from code

**Files to Modify:**
- Multiple files throughout codebase

---

- [ ] 4.14 Add Type Hints
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 8 hours
  **Dependencies:** None

  **Description:**
Add type hints to all public functions and methods.

**Acceptance Criteria:**
- Type hints on all function parameters
- Type hints on all return values
- mypy validation passes
- Type hints improve IDE autocomplete

**Files to Modify:**
- Multiple files throughout codebase

---


- [ ] 4.15 Split views.py into Modules
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 6 hours
  **Dependencies:** None

  **Description:**
Split monolithic views.py into separate modules by feature area.

**Acceptance Criteria:**
- views/auth.py for authentication views
- views/rooms.py for room management
- views/game.py for game actions
- views/profile.py for user profiles
- views/__init__.py imports all views
- All views still accessible

**Files to Modify:**
- `bingosync-app/bingosync/views.py` (split into multiple files)
- `bingosync-app/bingosync/views/` (create directory)

---

- [ ] 4.16 Add Docstrings
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 6 hours
  **Dependencies:** None

  **Description:**
Add docstrings to all public functions, classes, and methods.

**Acceptance Criteria:**
- Docstrings follow Google or NumPy style
- All public functions documented
- All classes documented
- All methods documented
- Parameters and return values described

**Files to Modify:**
- Multiple files throughout codebase

---

- [ ] 4.17 Set Up Linting with Ruff
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Set up ruff linter and achieve zero linting errors.

**Acceptance Criteria:**
- ruff added to requirements.txt
- ruff.toml configuration created
- All linting errors fixed
- Linting runs in CI pipeline
- Pre-commit hook optional

**Files to Modify:**
- `requirements.txt`
- `ruff.toml` (create)
- `.github/workflows/ci.yml`

---


## Phase 5: Polish & Production (Weeks 17-20)

- [ ] 5.1 Upgrade to Bootstrap 5
  **Priority:** Feature
  **Estimated Time:** 8 hours
  **Dependencies:** None

  **Description:**
Upgrade from Bootstrap 3 to Bootstrap 5.

**Acceptance Criteria:**
- Bootstrap 5 CSS and JS included
- All templates updated to Bootstrap 5 classes
- panel → card conversion
- btn-default → btn-secondary conversion
- All UI components work correctly
- Responsive design maintained

**Files to Modify:**
- `bingosync-app/templates/bingosync/*.html`
- `bingosync-app/static/bingosync/style.css`

---

- [ ] 5.2 Set Up Webpack Bundler
  **Priority:** Feature
  **Estimated Time:** 6 hours
  **Dependencies:** None

  **Description:**
Set up Webpack for JavaScript and CSS bundling.

**Acceptance Criteria:**
- webpack.config.js created
- Entry points defined for room, auth, profile
- Output bundles with content hashes
- Minification enabled
- Source maps for development
- npm scripts for build

**Files to Modify:**
- `package.json` (create)
- `webpack.config.js` (create)
- `bingosync-app/static/bingosync/` (restructure)

---

- [ ] 5.3 Implement Responsive Design
  **Priority:** Feature
  **Estimated Time:** 6 hours
  **Dependencies:** Task 5.1

  **Description:**
Ensure all pages work well on mobile devices.

**Acceptance Criteria:**
- Mobile-friendly navigation
- Board scales on small screens
- Forms usable on mobile
- Touch-friendly buttons
- Tested on multiple screen sizes

**Files to Modify:**
- `bingosync-app/templates/bingosync/*.html`
- `bingosync-app/static/bingosync/style.css`

---


- [ ] 5.4 Accessibility Improvements
  **Priority:** Feature
  **Estimated Time:** 6 hours
  **Dependencies:** Task 5.1

  **Description:**
Improve accessibility to meet WCAG 2.1 Level AA standards.

**Acceptance Criteria:**
- All images have alt text
- Form labels properly associated
- Keyboard navigation works
- Color contrast meets standards
- ARIA labels where needed
- Screen reader tested

**Files to Modify:**
- `bingosync-app/templates/bingosync/*.html`
- `bingosync-app/static/bingosync/style.css`

---

- [ ] 5.5 Add Loading Indicators
  **Priority:** Feature
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Add loading indicators for asynchronous operations.

**Acceptance Criteria:**
- Spinner shown during board generation
- Loading state for form submissions
- WebSocket connection status indicator
- Smooth transitions

**Files to Modify:**
- `bingosync-app/static/bingosync/room/board.js`
- `bingosync-app/templates/bingosync/bingosync.html`

---

- [ ] 5.6 Update Django to 4.2 LTS
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Update Django to version 4.2 LTS.

**Acceptance Criteria:**
- Django 4.2 in requirements.txt
- Deprecated features updated
- All tests pass
- No breaking changes

**Files to Modify:**
- `requirements.txt`
- Multiple files for compatibility

---


- [ ] 5.7 Update Tornado to Latest
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Update Tornado to the latest stable version.

**Acceptance Criteria:**
- Latest Tornado in requirements.txt
- Deprecated features updated
- WebSocket functionality works
- All tests pass

**Files to Modify:**
- `bingosync-websocket/requirements.txt`
- `bingosync-websocket/app.py`

---

- [ ] 5.8 Remove Python 2 Compatibility
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 2 hours
  **Dependencies:** None

  **Description:**
Remove six package and Python 2 compatibility code.

**Acceptance Criteria:**
- six package removed from requirements
- All six imports removed
- Python 3 syntax used throughout
- All tests pass

**Files to Modify:**
- `requirements.txt`
- Multiple files using six

---

- [ ] 5.9 Replace pytz with zoneinfo
  **Priority:** P2 (Code Quality)
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Replace pytz with Python's built-in zoneinfo module.

**Acceptance Criteria:**
- pytz removed from requirements
- zoneinfo imports added
- Timezone handling works correctly
- All tests pass

**Files to Modify:**
- `requirements.txt`
- Multiple files using pytz

---


- [ ] 5.10 Update Security-Critical Packages
  **Priority:** P0 (Security)
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Update all security-critical packages to latest versions.

**Acceptance Criteria:**
- certifi updated
- urllib3 updated
- cryptography updated
- safety check run
- No known vulnerabilities

**Files to Modify:**
- `requirements.txt`

---

- [ ] 5.11 Write README Documentation
  **Priority:** P3 (Documentation)
  **Estimated Time:** 6 hours
  **Dependencies:** Task 2.10

  **Description:**
Expand README with complete installation and deployment instructions.

**Acceptance Criteria:**
- Project description updated for HP CoS focus
- Prerequisites listed
- Installation instructions (Docker Compose)
- Environment variables documented
- Development setup instructions
- Production deployment guide
- Troubleshooting section

**Files to Modify:**
- `README.md`

---

- [ ] 5.12 Write API Documentation
  **Priority:** P3 (Documentation)
  **Estimated Time:** 6 hours
  **Dependencies:** None

  **Description:**
Document all API endpoints with request/response examples.

**Acceptance Criteria:**
- All endpoints documented
- Request parameters described
- Response formats shown
- Authentication requirements noted
- Error responses documented
- Examples provided

**Files to Modify:**
- `docs/API.md` (create)

---


- [ ] 5.13 Write WebSocket Protocol Documentation
  **Priority:** P3 (Documentation)
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Document the WebSocket protocol with message format specifications.

**Acceptance Criteria:**
- Connection process documented
- All message types documented
- Message format specifications
- Examples for each message type
- Error handling documented

**Files to Modify:**
- `docs/WEBSOCKET.md` (create)

---

- [ ] 5.14 Create Architecture Diagrams
  **Priority:** P3 (Documentation)
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Create architecture diagrams showing system components and data flow.

**Acceptance Criteria:**
- High-level architecture diagram
- Database schema diagram (ERD)
- WebSocket flow diagram
- Deployment architecture diagram
- Diagrams in docs/ directory

**Files to Modify:**
- `docs/architecture/` (create directory with diagrams)

---

- [ ] 5.15 Write CONTRIBUTING.md
  **Priority:** P3 (Documentation)
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Create CONTRIBUTING.md with development guidelines.

**Acceptance Criteria:**
- Code style guidelines
- Git workflow described
- Testing requirements
- Pull request process
- Issue reporting guidelines

**Files to Modify:**
- `CONTRIBUTING.md` (create)

---


- [ ] 5.16 Integrate Sentry
  **Priority:** Feature
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Integrate Sentry for error tracking and reporting.

**Acceptance Criteria:**
- sentry-sdk added to requirements
- Sentry initialized in settings.py
- SENTRY_DSN environment variable
- Errors reported to Sentry
- PII not sent to Sentry
- Environment tags set

**Files to Modify:**
- `requirements.txt`
- `bingosync-app/bingosync/settings.py`
- `.env.example`

---

- [ ] 5.17 Implement Structured Logging
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Add structured logging with appropriate log levels.

**Acceptance Criteria:**
- structlog added to requirements
- Logging configured in settings.py
- JSON log format
- Log levels used appropriately
- Authentication attempts logged
- Room events logged
- Role changes logged

**Files to Modify:**
- `requirements.txt`
- `bingosync-app/bingosync/settings.py`
- Multiple files for logging calls

---

- [ ] 5.18 Create Health Check Endpoints
  **Priority:** Feature
  **Estimated Time:** 3 hours
  **Dependencies:** None

  **Description:**
Add health check endpoints for Django and Tornado.

**Acceptance Criteria:**
- /health endpoint for Django
- /health endpoint for Tornado
- Database connectivity checked
- Redis connectivity checked
- JSON response with status
- 503 status on unhealthy

**Files to Modify:**
- `bingosync-app/bingosync/views.py`
- `bingosync-app/bingosync/urls.py`
- `bingosync-websocket/app.py`

---


- [ ] 5.19 Integrate Prometheus Metrics
  **Priority:** Feature
  **Estimated Time:** 4 hours
  **Dependencies:** None

  **Description:**
Expose Prometheus metrics for monitoring.

**Acceptance Criteria:**
- django-prometheus added to requirements
- Prometheus middleware configured
- /metrics endpoint exposed
- Request counts tracked
- Response times tracked
- Error rates tracked

**Files to Modify:**
- `requirements.txt`
- `bingosync-app/bingosync/settings.py`
- `bingosync-app/bingosync/urls.py`

---

- [ ] 5.20 Update Page Titles for HP CoS
  **Priority:** Feature
  **Estimated Time:** 2 hours
  **Dependencies:** None

  **Description:**
Update HTML page titles to indicate HP Chamber of Secrets focus.

**Acceptance Criteria:**
- All page titles updated
- "Bingosync" kept in titles
- "Harry Potter Chamber of Secrets" added
- Consistent branding across pages

**Files to Modify:**
- `bingosync-app/templates/bingosync/*.html`

---

- [ ] 5.21 Final Testing and Bug Fixes
  **Priority:** Feature
  **Estimated Time:** 16 hours
  **Dependencies:** All previous tasks

  **Description:**
Comprehensive testing and bug fixing before production deployment.

**Acceptance Criteria:**
- All features tested end-to-end
- All bugs documented and fixed
- Performance benchmarks met
- Security audit passed
- Documentation reviewed
- Ready for production

**Files to Modify:**
- Various files as bugs are found

---

## Summary

**Total Tasks:** 88
**Estimated Total Time:** ~310 hours (approximately 15-20 weeks with one developer)

**Phase Breakdown:**
- Phase 1 (Foundation & Security): 14 tasks, ~52 hours
- Phase 2 (Core Features): 13 tasks, ~60 hours
- Phase 3 (Advanced Features): 12 tasks, ~55 hours
- Phase 4 (Statistics & Quality): 17 tasks, ~90 hours
- Phase 5 (Polish & Production): 21 tasks, ~90 hours

**Priority Distribution:**
- P0 (Security): 10 tasks
- P1 (Performance): 5 tasks
- P2 (Code Quality): 18 tasks (includes HP CoS generator integration)
- P3 (Documentation): 5 tasks
- P4 (Testing): 6 tasks
- Feature: 44 tasks
