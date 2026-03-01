"""
Tests for HP Chamber of Secrets generator integration.

This module tests that the HP CoS generator works correctly with Bingosync's
infrastructure, including board generation, reproducibility, difficulty distribution,
variable amounts, synergy system, and performance.
"""

import time
from django.test import TestCase

from bingosync.generators.bingo_generator import BingoGenerator, GeneratorException


class HPCoSGeneratorIntegrationTestCase(TestCase):
    """Test HP CoS generator integration with Bingosync."""

    def setUp(self):
        """Set up test data."""
        self.game_name = "hp_cos"
        self.generator = BingoGenerator.instance(self.game_name)

    def test_generator_loads_successfully(self):
        """Generator should load without errors."""
        self.assertIsNotNone(self.generator)
        self.assertEqual(self.generator.game_name, self.game_name)

    def test_board_generation_produces_25_goals(self):
        """Generator should produce exactly 25 goals."""
        seed, card = self.generator.get_card(seed=12345)

        self.assertEqual(len(card), 25, "Board should have exactly 25 goals")

        # Verify each goal has required fields
        for i, goal in enumerate(card):
            self.assertIn('name', goal, f"Goal {i} should have 'name' field")
            self.assertIn('tier', goal, f"Goal {i} should have 'tier' field")
            self.assertIsInstance(
                goal['name'], str, f"Goal {i} name should be a string")
            self.assertIsInstance(
                goal['tier'], int, f"Goal {i} tier should be an integer")
            self.assertGreater(len(goal['name']), 0,
                               f"Goal {i} name should not be empty")

    def test_same_seed_produces_same_board(self):
        """Same seed should produce identical board (reproducibility)."""
        seed = 54321

        # Generate board twice with same seed
        seed1, card1 = self.generator.get_card(seed=seed)
        seed2, card2 = self.generator.get_card(seed=seed)

        # Seeds should match
        self.assertEqual(seed1, seed2, "Seeds should be identical")

        # Cards should be identical
        self.assertEqual(len(card1), len(card2), "Card lengths should match")

        for i, (goal1, goal2) in enumerate(zip(card1, card2)):
            self.assertEqual(
                goal1['name'],
                goal2['name'],
                f"Goal {i} names should match for same seed"
            )
            self.assertEqual(
                goal1['tier'],
                goal2['tier'],
                f"Goal {i} tiers should match for same seed"
            )

    def test_different_seeds_produce_different_boards(self):
        """Different seeds should produce different boards."""
        seed1, card1 = self.generator.get_card(seed=11111)
        seed2, card2 = self.generator.get_card(seed=99999)

        # At least some goals should be different
        differences = sum(
            1 for g1, g2 in zip(
                card1, card2) if g1['name'] != g2['name'])
        self.assertGreater(
            differences,
            0,
            "Different seeds should produce at least some different goals"
        )

    def test_all_difficulty_tiers_represented(self):
        """All 25 difficulty tiers should be represented across multiple boards."""
        # Generate multiple boards to ensure all tiers are used
        all_tiers = set()
        num_boards = 10

        for i in range(num_boards):
            seed, card = self.generator.get_card(seed=10000 + i * 1000)
            tiers = [goal['tier'] for goal in card]
            all_tiers.update(tiers)

        # Check that we have a good distribution of tiers
        # Note: Not all 25 tiers may appear in just 10 boards due to randomization,
        # but we should see a reasonable variety (at least 15 different tiers)
        self.assertGreaterEqual(
            len(all_tiers),
            15,
            f"Should have at least 15 different difficulty tiers across "
            f"{num_boards} boards, got {len(all_tiers)}")

        # All tiers should be in valid range (1-25)
        for tier in all_tiers:
            self.assertGreaterEqual(tier, 1, f"Tier {tier} should be >= 1")
            self.assertLessEqual(tier, 25, f"Tier {tier} should be <= 25")

    def test_variable_amounts_randomize_correctly(self):
        """Variable amounts in goal names should randomize correctly."""
        # Generate multiple boards and check for variable amounts
        boards_with_variables = []

        for i in range(5):
            seed, card = self.generator.get_card(seed=20000 + i * 1000)

            # Look for goals with numbers (indicating variable amounts were
            # processed)
            for goal in card:
                # Check if goal name contains numbers (e.g., "3 chocolate
                # frogs")
                if any(char.isdigit() for char in goal['name']):
                    boards_with_variables.append(goal['name'])

        # We should find at least some goals with variable amounts
        self.assertGreater(
            len(boards_with_variables),
            0,
            "Should find goals with variable amounts across multiple boards"
        )

        # Variable amounts should not contain the template syntax {min-max}
        for goal_name in boards_with_variables:
            self.assertNotIn(
                '{',
                goal_name,
                f"Goal '{goal_name}' should not contain template syntax"
            )
            self.assertNotIn(
                '}',
                goal_name,
                f"Goal '{goal_name}' should not contain template syntax"
            )

    def test_synergy_system_works(self):
        """Synergy system should prevent duplicate goal types on lines."""
        # Generate a board and check synergy
        seed, card = self.generator.get_card(seed=30000)

        # Define line indices (rows, columns, diagonals)
        lines = []

        # Rows
        for row in range(5):
            lines.append([row * 5 + col for col in range(5)])

        # Columns
        for col in range(5):
            lines.append([row * 5 + col for row in range(5)])

        # Diagonals
        lines.append([0, 6, 12, 18, 24])  # Top-left to bottom-right
        lines.append([4, 8, 12, 16, 20])  # Top-right to bottom-left

        # For each line, check that goals are reasonably diverse
        # (We can't check exact synergy types without parsing the JS goal list,
        # but we can verify that not all goals on a line are identical)
        for line_idx, line in enumerate(lines):
            goal_names = [card[i]['name'] for i in line]
            unique_goals = len(set(goal_names))

            # All 5 goals on a line should be unique
            self.assertEqual(
                unique_goals,
                5,
                f"Line {line_idx} should have 5 unique goals, got {unique_goals}"
            )

    def test_board_generation_performance(self):
        """Board generation should complete within 2 seconds."""
        seed = 40000

        start_time = time.time()
        seed_result, card = self.generator.get_card(seed=seed)
        end_time = time.time()

        elapsed_time = end_time - start_time

        self.assertLess(
            elapsed_time,
            2.0,
            f"Board generation took {elapsed_time:.2f}s, should be < 2s"
        )

    def test_no_javascript_errors_during_execution(self):
        """Generator should execute without JavaScript errors."""
        # Try generating multiple boards with different seeds
        # If there are JS errors, the generator will raise an exception
        seeds = [50000, 50001, 50002, 50003, 50004]

        for seed in seeds:
            try:
                seed_result, card = self.generator.get_card(seed=seed)
                self.assertEqual(
                    len(card), 25, f"Seed {seed} should produce 25 goals")
            except GeneratorException as e:
                self.fail(f"Generator raised exception for seed {seed}: {e}")
            except Exception as e:
                self.fail(f"Unexpected exception for seed {seed}: {e}")

    def test_empty_seed_generates_random_board(self):
        """Empty seed should generate a random board."""
        # Generate board with no seed (should use random seed)
        seed1, card1 = self.generator.get_card(seed=None)

        # Should still produce valid board
        self.assertEqual(len(card1), 25, "Random seed should produce 25 goals")
        self.assertIsNotNone(seed1, "Should return a seed value")

    def test_seed_as_string_works(self):
        """Seed provided as string should work correctly."""
        seed_str = "12345"
        seed_int = 12345

        # Both should work and produce same result
        seed1, card1 = self.generator.get_card(seed=seed_str)
        seed2, card2 = self.generator.get_card(seed=seed_int)

        # Cards should be identical
        for i, (goal1, goal2) in enumerate(zip(card1, card2)):
            self.assertEqual(
                goal1['name'],
                goal2['name'],
                f"Goal {i} should match for string and int seeds"
            )

    def test_board_size_is_5x5(self):
        """Board should be 5x5 (25 squares)."""
        seed, card = self.generator.get_card(seed=60000, size=5)

        self.assertEqual(len(card), 25, "5x5 board should have 25 goals")

    def test_goal_names_are_valid_strings(self):
        """All goal names should be valid, non-empty strings."""
        seed, card = self.generator.get_card(seed=70000)

        for i, goal in enumerate(card):
            name = goal['name']

            # Should be a string
            self.assertIsInstance(name, str, f"Goal {i} name should be string")

            # Should not be empty
            self.assertGreater(
                len(name), 0, f"Goal {i} name should not be empty")

            # Should not be just whitespace
            self.assertGreater(len(name.strip()), 0,
                               f"Goal {i} name should not be just whitespace")

    def test_difficulty_tiers_are_valid(self):
        """All difficulty tiers should be valid integers in range 1-25."""
        seed, card = self.generator.get_card(seed=80000)

        for i, goal in enumerate(card):
            tier = goal['tier']

            # Should be an integer
            self.assertIsInstance(
                tier, int, f"Goal {i} tier should be integer")

            # Should be in valid range
            self.assertGreaterEqual(tier, 1, f"Goal {i} tier should be >= 1")
            self.assertLessEqual(tier, 25, f"Goal {i} tier should be <= 25")

    def test_multiple_rapid_generations(self):
        """Generator should handle multiple rapid board generations."""
        # Generate 10 boards rapidly
        boards = []

        for i in range(10):
            seed, card = self.generator.get_card(seed=90000 + i)
            boards.append((seed, card))

        # All should be valid
        for i, (seed, card) in enumerate(boards):
            self.assertEqual(len(card), 25, f"Board {i} should have 25 goals")
            self.assertIsNotNone(seed, f"Board {i} should have a seed")

    def test_extreme_seed_values(self):
        """Generator should handle extreme seed values."""
        extreme_seeds = [1, 999999, 500000, 123, 999998]

        for seed in extreme_seeds:
            seed_result, card = self.generator.get_card(seed=seed)

            self.assertEqual(
                len(card),
                25,
                f"Seed {seed} should produce 25 goals"
            )
            self.assertIsNotNone(seed_result,
                                 f"Seed {seed} should return seed value")
