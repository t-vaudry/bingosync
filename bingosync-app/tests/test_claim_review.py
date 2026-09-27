"""
Tests for the claim review system (Task 3.6)
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from bingosync.models.rooms import Room, Game, Player, Square
from bingosync.models.enums import Role
from bingosync.models.colors import Color
from bingosync.models.game_type import GameType
from bingosync.models.events import ClaimReviewEvent
import json

User = get_user_model()


class ClaimReviewEndpointTest(TestCase):
    """Test the review_claim endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        # Create users
        self.gamemaster_user = User.objects.create_user(
            username='gamemaster',
            email='gm@test.com',
            password='testpass123'
        )
        self.player_user = User.objects.create_user(
            username='player1',
            email='player1@test.com',
            password='testpass123'
        )
        self.counter_user = User.objects.create_user(
            username='counter1',
            email='counter1@test.com',
            password='testpass123'
        )

        # Create room
        self.room = Room.objects.create(
            name='Test Room',
            room_code='TEST01',
            passphrase='test123'
        )

        # Create game
        board_json = [{"name": f"Goal {i}", "tier": i % 5} for i in range(1, 26)]
        self.game = Game.from_board(
            board_json,
            room=self.room,
            game_type_value=GameType.hp_cos.value,
            lockout_mode_value=1,
            seed=12345,
            fog_of_war=False
        )
        self.room.save()

        # Create players
        self.gamemaster = Player.objects.create(
            room=self.room,
            user=self.gamemaster_user,
            name='Gamemaster',
            role=Role.GAMEMASTER,
            color_value=Color.orange.value
        )

        self.player = Player.objects.create(
            room=self.room,
            user=self.player_user,
            name='Player1',
            role=Role.PLAYER,
            color_value=Color.red.value
        )

        self.counter = Player.objects.create(
            room=self.room,
            user=self.counter_user,
            name='Counter1',
            role=Role.COUNTER,
            color_value=Color.blue.value,
            monitoring_player=self.player
        )

        # Create client
        self.client = Client()

    def test_counter_can_review_claim_under_review(self):
        """Test that counter can mark a claim as under review"""
        # Login as counter
        self.client.login(username='counter1', password='testpass123')

        # Mark a square as claimed by the player
        square = self.game.squares[0]
        square.claimed_by = self.player
        square.claim_status = 'pending_decision'
        square_color = square.color
        square_color.add(self.player.color)
        square.color = square_color
        square.save()

        # Save session player
        session = self.client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: self.counter.encoded_uuid}
        session.save()

        # Review the claim as "under review"
        response = self.client.post(
            '/api/review-claim',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': 1,
                'action': 'under_review'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify the square status was updated
        square.refresh_from_db()
        self.assertEqual(square.claim_status, 'under_review')
        self.assertEqual(square.reviewed_by, self.counter)

        # Verify event was created
        self.assertTrue(
            ClaimReviewEvent.objects.filter(
                player=self.counter,
                square=square,
                action='under_review'
            ).exists()
        )

    def test_counter_can_confirm_claim(self):
        """Test that counter can confirm a claim"""
        # Login as counter
        self.client.login(username='counter1', password='testpass123')

        # Mark a square as claimed by the player
        square = self.game.squares[1]
        square.claimed_by = self.player
        square.claim_status = 'pending_decision'
        square_color = square.color
        square_color.add(self.player.color)
        square.color = square_color
        square.save()

        # Save session player
        session = self.client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: self.counter.encoded_uuid}
        session.save()

        # Confirm the claim
        response = self.client.post(
            '/api/review-claim',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': 2,
                'action': 'confirm'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify the square status was updated
        square.refresh_from_db()
        self.assertEqual(square.claim_status, 'confirmed')
        self.assertEqual(square.reviewed_by, self.counter)

    def test_counter_can_reject_claim(self):
        """Test that counter can reject a claim and remove the color"""
        # Login as counter
        self.client.login(username='counter1', password='testpass123')

        # Mark a square as claimed by the player
        square = self.game.squares[2]
        square.claimed_by = self.player
        square.claim_status = 'pending_decision'
        square_color = square.color
        square_color.add(self.player.color)
        square.color = square_color
        square.save()

        # Save session player
        session = self.client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: self.counter.encoded_uuid}
        session.save()

        # Reject the claim
        response = self.client.post(
            '/api/review-claim',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': 3,
                'action': 'reject'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)

        # Verify the square status was updated and color removed
        square.refresh_from_db()
        self.assertEqual(square.claim_status, 'rejected')
        self.assertEqual(square.reviewed_by, self.counter)
        self.assertIsNone(square.claimed_by)
        self.assertNotIn(self.player.color, square.color.colors)

    def test_non_counter_cannot_review_claim(self):
        """Test that non-counter players cannot review claims"""
        # Login as regular player
        self.client.login(username='player1', password='testpass123')

        # Mark a square as claimed
        square = self.game.squares[3]
        square.claimed_by = self.player
        square.claim_status = 'pending_decision'
        square.save()

        # Save session player
        session = self.client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: self.player.encoded_uuid}
        session.save()

        # Try to review the claim
        response = self.client.post(
            '/api/review-claim',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': 4,
                'action': 'confirm'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 403)

    def test_counter_cannot_review_unassigned_player_claim(self):
        """Test that counter can only review claims from assigned players"""
        # Create another player not assigned to this counter
        other_player_user = User.objects.create_user(
            username='player2',
            email='player2@test.com',
            password='testpass123'
        )
        other_player = Player.objects.create(
            room=self.room,
            user=other_player_user,
            name='Player2',
            role=Role.PLAYER,
            color_value=Color.green.value
        )

        # Login as counter
        self.client.login(username='counter1', password='testpass123')

        # Mark a square as claimed by the other player
        square = self.game.squares[4]
        square.claimed_by = other_player
        square.claim_status = 'pending_decision'
        square_color = square.color
        square_color.add(other_player.color)
        square.color = square_color
        square.save()

        # Save session player
        session = self.client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: self.counter.encoded_uuid}
        session.save()

        # Try to review the claim
        response = self.client.post(
            '/api/review-claim',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': 5,
                'action': 'confirm'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_action_rejected(self):
        """Test that invalid actions are rejected"""
        # Login as counter
        self.client.login(username='counter1', password='testpass123')

        # Mark a square as claimed
        square = self.game.squares[5]
        square.claimed_by = self.player
        square.claim_status = 'pending_decision'
        square.save()

        # Save session player
        session = self.client.session
        session['authorized_rooms'] = {self.room.encoded_uuid: self.counter.encoded_uuid}
        session.save()

        # Try to review with invalid action
        response = self.client.post(
            '/api/review-claim',
            data=json.dumps({
                'room': self.room.encoded_uuid,
                'slot': 6,
                'action': 'invalid_action'
            }),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 400)
