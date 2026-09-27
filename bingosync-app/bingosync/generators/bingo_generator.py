import json
import logging
import os
import subprocess
import re
import tempfile

from bingosync.settings import GENERATOR_TIMEOUT_SECONDS


logger = logging.getLogger(__name__)

GEN_DIR = "generators"
GEN_NAME_TEMPL = "{}_generator.js"

PREFERRED_SIZE_RE = re.compile(r'generator-preferred-size: (\d)+')


def load_generator(game_name):
    filename = os.path.join(GEN_DIR, GEN_NAME_TEMPL.format(game_name))
    with open(filename) as js_file:
        return BingoGenerator(game_name, js_file.read())


class GeneratorException(Exception):
    pass


class BingoGenerator:
    CACHED_INSTANCES = {}

    @staticmethod
    def loaded(game_name):
        return game_name in BingoGenerator.CACHED_INSTANCES

    @staticmethod
    def instance(game_name):
        if game_name not in BingoGenerator.CACHED_INSTANCES:
            BingoGenerator.CACHED_INSTANCES[game_name] = load_generator(
                game_name)
        return BingoGenerator.CACHED_INSTANCES[game_name]

    @staticmethod
    def reload(game_name):
        BingoGenerator.CACHED_INSTANCES[game_name] = load_generator(game_name)

    def __init__(self, game_name, generator_js, goal_list_js=None):
        self.game_name = game_name
        self.generator_js_bytes = generator_js.encode("utf-8")

        match = PREFERRED_SIZE_RE.search(generator_js)
        self.preferred_size = int(match.group(1)) if match else 5

    def validate_custom_json(self, custom_json, size=5):
        return []

    def eval(self, js_command):
        js_eval = "\nconsole.log(JSON.stringify(" + js_command + "));"
        full_command = self.generator_js_bytes + js_eval.encode("utf-8")

        # Write to temp file in GEN_DIR so require() paths work correctly
        try:
            with tempfile.NamedTemporaryFile(
                mode='wb', suffix='.js', delete=False, dir=GEN_DIR
            ) as temp_file:
                temp_file.write(full_command)
                temp_file_path = temp_file.name

            try:
                out = subprocess.check_output(
                    ["node", temp_file_path], 
                    timeout=GENERATOR_TIMEOUT_SECONDS, 
                    cwd=GEN_DIR,
                    stderr=subprocess.STDOUT
                )
            except subprocess.CalledProcessError as e:
                error_output = e.output.decode("utf-8") if e.output else "No error output"
                error_message = (
                    f"Generator '{self.game_name}' failed with exit code {e.returncode}. "
                    f"Error output: {error_output}"
                )
                logger.error(error_message)
                raise GeneratorException(error_message)
            finally:
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass
        except subprocess.TimeoutExpired:
            error_message = f"Took too long to generate a bingo board for game '{self.game_name}'"
            logger.error(error_message)
            raise GeneratorException(error_message)

        return json.loads(out.decode("utf-8"))

    def get_card(self, seed=None, custom_board=None, size=5):
        if isinstance(size, str) and not size:
            size = self.preferred_size
        size = int(size)

        opts = {"size": size}
        if seed is not None:
            # the generator *actually* treats the seed as a string
            opts["seed"] = str(seed)
        if custom_board is not None:
            opts["custom_board"] = custom_board

        js_command = "bingoGenerator(bingoList, " + json.dumps(opts) + ")"
        card = self.eval(js_command)

        return process_card(card, seed, size)


def process_card(card, seed, size):
    # the regular SRL generator includes an extra null element at the front,
    # so ignore that

    seed = card['seed']
    card = card['objectives']

    if len(card) == (size * size) + 1:
        card = card[1:]
    if len(card) != size * size:
        raise Exception("bad card length: "
                        + str(len(card)) + ", card: " + str(card))
    x = [{"name": goal.get("name", ""), "tier": goal.get(
        "difficulty", "") or 0} for goal in card]
    return seed, x
