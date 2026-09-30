"""Check GitHub releases for a newer plugin version and notify once."""
import json
import logging
import os
import time
import urllib.request

from .ui import notify

log = logging.getLogger(__name__)

RELEASES_URL = 'https://api.github.com/repos/Tsifrokayf/kodi-yandexmusic/releases/latest'
STATE_FILE = 'update_state.json'
CHECK_INTERVAL = 12 * 3600
TIMEOUT = 4


def version_tuple(text):
    parts = []
    for chunk in str(text or '').strip().lstrip('vV').split('.'):
        digits = ''
        for char in chunk:
            if not char.isdigit():
                break
            digits += char
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _load_state(profile):
    try:
        with open(os.path.join(profile, STATE_FILE), encoding='utf-8') as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def _save_state(profile, state):
    try:
        with open(os.path.join(profile, STATE_FILE), 'w', encoding='utf-8') as handle:
            json.dump(state, handle)
    except OSError:
        log.debug('cannot persist update state', exc_info=True)


def check_for_update(ctx):
    """Notify about a newer release; probes at most every 12h, notifies once."""
    state = _load_state(ctx.profile)
    now = time.time()
    try:
        checked = float(state.get('checked') or 0)
    except (TypeError, ValueError):
        checked = 0.0
    if now - checked < CHECK_INTERVAL:
        return
    try:
        request = urllib.request.Request(
            RELEASES_URL, headers={'User-Agent': 'kodi-yandexmusic-plugin'})
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.load(response)
    except Exception:
        log.debug('release check failed', exc_info=True)
        state['checked'] = now
        _save_state(ctx.profile, state)
        return
    state['checked'] = now
    latest = str(data.get('tag_name') or '').strip().lstrip('vV')
    current = str(ctx.addon.getAddonInfo('version') or '0')
    if latest and version_tuple(latest) > version_tuple(current) \
            and state.get('seen') != latest:
        state['seen'] = latest
        _save_state(ctx.profile, state)
        try:
            message = ctx.L(30113) % (latest, current)
        except (TypeError, ValueError):
            message = '{0} ({1})'.format(latest, current)
        notify(ctx, ctx.L(30112), message, sound=False)
    else:
        _save_state(ctx.profile, state)
