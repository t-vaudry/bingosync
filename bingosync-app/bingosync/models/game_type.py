from enum import Enum, unique


@unique
class GameType(Enum):
    hp_cos = 50

    def __str__(self):
        return self.short_name

    @property
    def group(self):
        return GAME_TYPE_GROUPS[self]

    @property
    def group_name(self):
        return GAME_TYPE_GROUP_NAMES[self]

    @property
    def long_name(self):
        return GAME_TYPE_LONG_NAMES[self]

    @property
    def short_name(self):
        return GAME_TYPE_SHORT_NAMES[self]

    @property
    def variant_name(self):
        return GAME_TYPE_VARIANT_NAMES[self]

    @property
    def is_game_group(self):
        return self.group == self

    @property
    def is_custom(self):
        return False  # HP CoS is not a custom game type

    @property
    def uses_seed(self):
        return True  # HP CoS uses a seed

    @staticmethod
    def for_value(value):
        # Since we only have one game type, always return hp_cos
        # This maintains compatibility with existing code that passes value=50
        if value == 50:
            return GameType.hp_cos
        # For backward compatibility, if someone passes a different value,
        # still return HP CoS
        return GameType.hp_cos

    def generator_instance(self):
        from bingosync.generators import BingoGenerator
        return BingoGenerator.instance(self.name)

    @staticmethod
    def choices():
        return [(game_type.value, game_type.long_name)
                for game_type in GameType]

    @staticmethod
    def game_choices():
        # Return only HP CoS as the game choice
        return [(None, ''), (GameType.hp_cos.value,
                             GAME_TYPE_GROUP_NAMES[GameType.hp_cos])]

    @staticmethod
    def variant_choices():
        # Return only HP CoS variant
        return [(GameType.hp_cos.value, [(GameType.hp_cos.value,
                 GAME_TYPE_VARIANT_NAMES[GameType.hp_cos])])]


# Simplified game groups - only HP Chamber of Secrets
GAME_GROUPS = {
    GameType.hp_cos: {
        "name": "Harry Potter and the Chamber of Secrets",
        "variants": [
            (GameType.hp_cos, "Normal", "HP CoS"),
        ],
    }
}

# Build lookup dictionaries from GAME_GROUPS
GAME_TYPE_GROUPS = {}
GAME_TYPE_GROUP_NAMES = {}
GAME_TYPE_LONG_NAMES = {}
GAME_TYPE_SHORT_NAMES = {}
GAME_TYPE_VARIANT_NAMES = {}
ALL_VARIANTS = []

for group, entry in GAME_GROUPS.items():
    name = entry["name"]
    variants = entry["variants"]

    for variant_tuple in variants:
        game_type = variant_tuple[0]
        variant_name = variant_tuple[1]
        short_name = variant_tuple[2]

        GAME_TYPE_GROUPS[game_type] = group
        GAME_TYPE_GROUP_NAMES[game_type] = name
        GAME_TYPE_LONG_NAMES[game_type] = name + " - " + \
            variant_name if variant_name != "Normal" else name
        GAME_TYPE_SHORT_NAMES[game_type] = short_name
        GAME_TYPE_VARIANT_NAMES[game_type] = variant_name
        ALL_VARIANTS.append(game_type)
