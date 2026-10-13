from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe
from numbers import Number

import json

register = template.Library()


@register.filter
def num_goals(game, color):
    return len([square for square in game.squares if square.color == color])


@register.filter
def hovertext_game_type(game_type):
    title = escape(game_type.long_name)
    short_name = escape(str(game_type))
    return mark_safe('<span title="' + title + '">' + short_name + '</span>')


@register.filter
def format_js_val(value):
    if value is True:
        return "true"
    elif value is False:
        return "false"
    elif isinstance(value, Number):
        return value
    else:
        return '"' + value + '"'


@register.filter
def jsonify(d):
    return json.dumps(d)


@register.filter
def color_label(room, color):
    """A color's name in the room: its player's name when exactly one player
    uses it, otherwise the color's name (see Room.color_label)."""
    return room.color_label(color)
