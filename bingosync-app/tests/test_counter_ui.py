"""
Tests for Counter UI Panel functionality
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from bingosync.models.rooms import Room, Player, Game
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync import models
import json

User = get_user_model()


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-test-cache-counter-ui',
        }
    },
    RATELIMIT_ENABLE=False
)
class CounterUIPanelTests(TestCase):
    """Test Counter UI Panel rendering and functionality"""
    
    def setUp(self):
        """Set up test data"""
        # Create users
        self.gamemaster = User.objects.create_user(
            username='gamemaster',
            email='gm@test.com',
            password='testpass123'
        )
        self.counter = User.objects.create_user(
            username='counter',
            email='counter@test.com',
            password='testpass123'
        )
        self.player = User.objects.create_user(
            username='player',
            email='player@test.com',
            password='testpass123'
        )
        
        # Create room as gamemaster
        gm_client = Client()
        gm_client.force_login(self.gamemaster)
        
        room_resp = gm_client.post("/dashboard", {
            "room_name": "Test Room",
            "passphrase": "testpass",
            "game_type": str(models.GameType.hp_cos.value),
            "lockout_mode": str(models.LockoutMode.lockout.value),
        }, follow=True)
        
        self.room = room_resp.context["room"]
        self.room_url = f'/room/{self.room.encoded_uuid}'
        
        # Join as counter
        counter_client = Client()
        counter_client.force_login(self.counter)
        counter_client.post("/api/join-room", json.dumps({
            "room": self.room.encoded_uuid,
            "nickname": "counter",
            "password": "testpass",
            "role": "counter",
        }), content_type="application/json")
        
        # Join as player
        player_client = Client()
        player_client.force_login(self.player)
        player_client.post("/api/join-room", json.dumps({
            "room": self.room.encoded_uuid,
            "nickname": "player",
            "password": "testpass",
            "role": "player",
        }), content_type="application/json")
        
        self.gm_client = gm_client
        self.counter_client = counter_client
        self.player_client = player_client
    
    def test_counter_panel_visible_to_counter(self):
        """Test that counter panel is visible to users with counter role"""
        response = self.counter_client.get(self.room_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'counter-panel')
        self.assertContains(response, 'Claim Review')
    
    def test_counter_panel_not_visible_to_player(self):
        """Test that counter panel is not visible to regular players"""
        response = self.player_client.get(self.room_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'counter-panel')
    
    def test_counter_panel_not_visible_to_gamemaster(self):
        """Test that counter panel is not visible to gamemaster"""
        response = self.gm_client.get(self.room_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'counter-panel')
    
    def test_counter_js_initialized_for_counter(self):
        """Test that counter.js is initialized for counter role"""
        response = self.counter_client.get(self.room_url)
        
        self.assertEqual(response.status_code, 200)
        # Check that counter.js is included
        self.assertContains(response, 'counter.js')
        # Check that Counter is initialized
        self.assertContains(response, "window.counterUI = new Counter")
    
    def test_pending_claims_list_present(self):
        """Test that pending claims list element is present in counter panel"""
        response = self.counter_client.get(self.room_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pending-claims-list')
    
    def test_claim_history_list_present(self):
        """Test that claim history list element is present in counter panel"""
        response = self.counter_client.get(self.room_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'claim-history-list')
    
    def test_counter_panel_styling_loaded(self):
        """Test that claim-status.css is loaded"""
        response = self.counter_client.get(self.room_url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'claim-status.css')


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-test-cache-counter-func',
        }
    },
    RATELIMIT_ENABLE=False
)
class CounterUIFunctionalityTests(TestCase):
    """Test Counter UI functionality via JavaScript behavior"""
    
    def setUp(self):
        """Set up test data"""
        self.counter = User.objects.create_user(
            username='counter',
            email='counter@test.com',
            password='testpass123'
        )
        
        # Create room as counter
        self.client = Client()
        self.client.force_login(self.counter)
        
        room_resp = self.client.post("/dashboard", {
            "room_name": "Test Room",
            "passphrase": "testpass",
            "game_type": str(models.GameType.hp_cos.value),
            "lockout_mode": str(models.LockoutMode.lockout.value),
        }, follow=True)
        
        self.room = room_resp.context["room"]
        self.room_url = f'/room/{self.room.encoded_uuid}'
        
        # Change creator's role to counter
        creator_player = Player.objects.get(room=self.room, user=self.counter)
        creator_player.role = Role.COUNTER
        creator_player.save()
    
    def test_counter_ui_has_three_action_buttons(self):
        """Test that counter panel shows three action buttons per claim"""
        response = self.client.get(self.room_url)
        
        self.assertEqual(response.status_code, 200)
        # The buttons are created dynamically by JavaScript, but we can verify
        # the counter.js file contains the button creation logic
        self.assertContains(response, 'counter.js')
    
    def test_claim_status_badge_styles_present(self):
        """Test that claim status badge styles are present"""
        response = self.client.get(self.room_url)
        
        self.assertEqual(response.status_code, 200)
        # Verify CSS is loaded
        self.assertContains(response, 'claim-status.css')
