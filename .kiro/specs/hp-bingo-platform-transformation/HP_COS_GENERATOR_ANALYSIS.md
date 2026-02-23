# HP Chamber of Secrets Generator Analysis

## Overview

The HP CoS generator provided in the temp directory is fully compatible with Bingosync's generator architecture. It follows the standard pattern used by all Bingosync generators and requires minimal adaptation.

## Generator Structure

### File: generator.js

The generator implements the standard Bingosync generator pattern:

1. **Seedrandom Library**: Uses Math.seedrandom() for reproducible randomization
2. **bingoGenerator Function**: Main export that takes bingoList and options
3. **Difficulty Calculation**: Each board position (1-25) gets a calculated difficulty tier
4. **Goal Selection**: Uses Box-Muller distribution to select goals from appropriate tiers
5. **Synergy System**: Prevents similar goals from appearing on the same row/column/diagonal

### File: goal-list.js

Contains the complete goal database with 25 difficulty tiers:

- **Tier 1**: Easiest goals (e.g., "All 16 beans on Lockhart's balcony")
- **Tier 25**: Hardest goals (e.g., "Harry Potter Wizard Card", "27-33 Bronze Wizard Cards")
- **Total Goals**: ~100+ unique goals across all tiers
- **Lockout Mode**: 6 special goals for lockout mode

## Goal Properties

Each goal includes:

```javascript
{
    "id": "unique-identifier",
    "name": "Display name with optional {variables}",
    "difficulty": 1-25,
    "amount": 1,  // Base amount
    "types": {
        "castle": 1,  // Synergy type
        "selfsynergy": 0  // Self-synergy penalty
    },
    "triggers": ["other-goal-ids"],  // Dependencies
    "rowtypes": {
        "card": 0,  // Wizard card count
        "bean": 0,  // Bean count
        "star": 0   // Challenge star count
    }
}
```

## Special Features

### Variable Amounts

Goals can have dynamic amounts using special syntax:

- `{min-max}`: Random number between min and max
  - Example: "{3-4} chocolate frogs" → "3 chocolate frogs" or "4 chocolate frogs"
- `{opt1,opt2,opt3}`: Random choice from options
  - Example: "Cast at {5,6,7} Gargoyles" → "Cast at 5 Gargoyles"

### Synergy System

The synergy system ensures board variety:

- Goals have `types` like "castle", "skurge", "diffindo", "multi", "cards", etc.
- When placing a goal, the generator checks all goals on intersecting lines
- Goals with matching types increase synergy score
- The generator selects the goal with lowest synergy
- `selfsynergy` creates negative synergy to encourage/discourage certain combinations

Example synergy types:
- `castle`: Goals in Hogwarts castle
- `skurge`: Goals in Skurge Challenge
- `diffindo`: Goals in Diffindo Challenge
- `multi`: Goals that span multiple areas
- `cards`: Wizard card collection goals
- `duels`: Goals requiring dueling

### Triggers

Some goals have `triggers` that create dependencies:

- `"triggers": ["completion-stars"]`: This goal counts toward completion star goals
- `"triggers": ["cards-23", "cards-37"]`: This goal counts toward card collection goals
- `"triggers": ["matches-6"]`: This goal counts toward match goals

## Integration with Bingosync

### Current Bingosync Generator Pattern

Bingosync generators follow this pattern:

```javascript
// Generator file
bingoGenerator = function(bingoList, opts) {
    var SEED = opts.seed || Math.ceil(999999 * Math.random()).toString();
    var MODE = opts.mode || "normal";
    var LANG = opts.lang || 'name';
    
    // ... generation logic ...
    
    return bingoBoard;  // Array of 25 goal objects
}

module.exports = bingoGenerator;
```

```javascript
// Goal list file
var bingoList = {
    "normal": {
        "1": [/* goals */],
        // ... tiers 2-25
    },
    "lockout": [/* lockout goals */]
};

module.exports = bingoList;
```

### HP CoS Generator Compatibility

The HP CoS generator is **already compatible**:

✅ Exports `bingoGenerator` function
✅ Takes `bingoList` and `opts` parameters
✅ Returns array of 25 goal objects
✅ Supports seed-based generation
✅ Supports "normal" and "lockout" modes
✅ Uses standard goal object format

### Required Adaptations

**Minimal changes needed:**

1. **File Naming**: 
   - Rename `generator.js` → `hp_cos_generator.js`
   - Rename `goal-list.js` → `hp_cos_goal_list.js`

2. **Module Structure**:
   - Ensure proper module.exports at end of files
   - Link generator to goal list

3. **Python Integration**:
   - Update `bingosync/generators.py` to invoke HP CoS generator
   - Remove references to other game types

## Testing Strategy

### Unit Tests

Test the generator's core functionality:

```python
def test_hp_cos_generator_reproducibility():
    """Same seed should produce same board"""
    board1 = generate_board(seed=12345)
    board2 = generate_board(seed=12345)
    assert board1 == board2

def test_hp_cos_generator_difficulty_distribution():
    """All difficulty tiers should be represented"""
    boards = [generate_board(seed=i) for i in range(100)]
    difficulties = set()
    for board in boards:
        for goal in board:
            difficulties.add(goal['difficulty'])
    assert len(difficulties) == 25  # All tiers used

def test_hp_cos_generator_variable_amounts():
    """Variable amounts should randomize correctly"""
    boards = [generate_board(seed=i) for i in range(100)]
    # Check that {3-4} produces both 3 and 4
    amounts = set()
    for board in boards:
        for goal in board:
            if 'chocolate frogs' in goal['name']:
                amount = int(goal['name'].split()[0])
                amounts.add(amount)
    assert 3 in amounts and 4 in amounts

def test_hp_cos_generator_synergy():
    """Similar goals should not appear on same line"""
    board = generate_board(seed=12345)
    # Check each row, column, diagonal
    for line in get_all_lines():
        types = [board[i]['types'] for i in line]
        # No duplicate types on same line
        assert len(types) == len(set(types))
```

### Integration Tests

Test with Bingosync infrastructure:

```python
def test_hp_cos_generator_subprocess():
    """Generator should work via subprocess"""
    result = subprocess.run(
        ['node', 'generators/hp_cos_generator.js', '12345'],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    board = json.loads(result.stdout)
    assert len(board) == 25

def test_hp_cos_generator_performance():
    """Generator should complete within 2 seconds"""
    start = time.time()
    board = generate_board(seed=12345)
    duration = time.time() - start
    assert duration < 2.0
```

## Implementation Plan

### Phase 1: File Integration (Task 1.12)

1. Copy generator.js to `bingosync-app/generators/hp_cos_generator.js`
2. Copy goal-list.js to `bingosync-app/generators/hp_cos_goal_list.js`
3. Ensure proper module.exports
4. Test standalone execution: `node hp_cos_generator.js 12345`

### Phase 2: Python Integration (Task 1.12)

1. Update `bingosync/generators.py`:
   ```python
   def generate_hp_cos_board(seed):
       result = subprocess.run(
           ['node', 'generators/hp_cos_generator.js', str(seed)],
           capture_output=True,
           text=True,
           timeout=10,
           cwd=settings.GENERATOR_DIR
       )
       if result.returncode != 0:
           raise GeneratorException(result.stderr)
       return json.loads(result.stdout)
   ```

2. Remove other generator references
3. Update views to use HP CoS generator

### Phase 3: Testing (Task 1.13)

1. Write unit tests for generator
2. Write integration tests with Bingosync
3. Test with multiple seeds
4. Verify variable amounts work
5. Verify synergy system works
6. Performance testing

## Conclusion

The HP CoS generator is production-ready and requires minimal adaptation to work with Bingosync. The main work is:

1. File renaming and placement
2. Removing other generators
3. Updating Python integration code
4. Comprehensive testing

Estimated time: 10 hours total (Tasks 1.11, 1.12, 1.13)
