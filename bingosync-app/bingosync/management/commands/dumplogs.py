from bingosync import models
import sys
import json

from django.core.management.base import BaseCommand

# hint: eval "cd $(sudo systemctl show bingosync | grep ^WorkingDirectory=
# | cut -d= -f2-); sudo -u bingosync $(sudo systemctl show bingosync |
# grep ^Environment= | cut -d= -f2-) python manage.py dumplogs"
# >bingosync_archive.ndjson


class Command(BaseCommand):
    help = 'Generates a ndjson file with the full log for every room'

    def add_arguments(self, parser):
        parser.add_argument(
            "-o",
            dest="filename",
            default=None,
            help="File to output to")

    def handle(self, *args, **options):
        filename = options["filename"]
        if filename is None or filename == "-":
            fp = sys.stdout
        else:
            fp = open(filename, 'w')

        for room in models.Room.objects.all():
            games = list(room.games)
            events = models.Event.get_all_for_room(room)
            for game, next_game in zip(games, games[1:] + [None]):
                game_events = [
                    e.to_json() for e in events if e.timestamp >= game.created_date and (
                        next_game is None or e.timestamp < next_game.created_date)]
                players = {e["player"]["uuid"]: e["player"]
                           for e in game_events}
                for e in game_events:
                    e["player"] = e["player"]["uuid"]
                    if "square" in e:
                        e["square"] = e["square"]["slot"]
                line = {
                    "room": str(
                        room.uuid),
                    "players": players,
                    "board": game.board,
                    "events": game_events}
                json.dump(line, fp)
                fp.write('\n')
