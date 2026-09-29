"""Helpers for building and parsing plugin URLs (pure, testable)."""
from urllib.parse import parse_qsl, urlencode

ADDON_ID = 'plugin.audio.yandexmusic'
BASE_URL = 'plugin://' + ADDON_ID


def build_url(base_url, action, **params):
    data = {'action': action}
    for key, value in params.items():
        if value is None or value == '':
            continue
        data[key] = str(value)
    return '{base}?{query}'.format(base=base_url, query=urlencode(data))


def parse_params(query_string):
    if not query_string:
        return {}
    return dict(parse_qsl(query_string.lstrip('?'), keep_blank_values=True))
