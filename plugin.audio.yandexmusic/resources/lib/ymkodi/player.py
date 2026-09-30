"""Playback: resolve direct stream URL and hand it to Kodi."""
import json
import logging
import os

import xbmc
import xbmcplugin

from . import audiocache
from .api import StreamError
from .auth import NotAuthorized
from .ui import notify, track_artists, track_listitem
from .urls import build_url

log = logging.getLogger(__name__)

PLAY_STATE_FILE = 'play_state.json'


def save_play_state(ctx, track_id, track):
    """Remember the last started track (used by karaoke/lyrics shortcuts)."""
    artists = track_artists(track)
    state = {
        'track': track_id,
        'title': getattr(track, 'title', None) or '',
        'artists': artists,
    }
    try:
        with open(os.path.join(ctx.profile, PLAY_STATE_FILE), 'w', encoding='utf-8') as handle:
            json.dump(state, handle, ensure_ascii=False)
    except OSError:
        log.debug('cannot persist play state', exc_info=True)


def read_play_state(ctx):
    """Last started track state or None."""
    try:
        with open(os.path.join(ctx.profile, PLAY_STATE_FILE), encoding='utf-8') as handle:
            state = json.load(handle)
    except (OSError, ValueError):
        return None
    if isinstance(state, dict) and state.get('track'):
        return state
    return None


def play(ctx, params):
    track_id = params.get('track') or ''
    station = params.get('station')
    batch_id = params.get('batch')

    try:
        url, track = ctx.service.resolve_stream(track_id)
        if params.get('wave'):
            try:
                ctx.service.wave_track_started(params.get('wave'),
                                               batch_id or params.get('batch'),
                                               track_id)
            except Exception:
                log.debug('wave trackStarted feedback failed', exc_info=True)
        elif station:
            ctx.service.radio_track_started(station, track_id, batch_id=batch_id)
    except NotAuthorized:
        notify(ctx, ctx.L(30010), ctx.L(30019))
        xbmcplugin.setResolvedUrl(ctx.handle, False, track_placeholder())
        return
    except StreamError as error:
        log.info('stream error for %s: %s', track_id, error)
        notify(ctx, ctx.L(30090), ctx.L(30091))
        xbmcplugin.setResolvedUrl(ctx.handle, False, track_placeholder())
        return
    except Exception:
        log.exception('unexpected playback error for %s', track_id)
        notify(ctx, ctx.L(30090), str(track_id))
        xbmcplugin.setResolvedUrl(ctx.handle, False, track_placeholder())
        return

    path = None
    save_play_state(ctx, track_id, track)
    if not station and ctx.addon.getSetting('preload_track') != 'false':
        cached = audiocache.cached_path(ctx.profile, track_id)
        if audiocache.is_fresh(cached):
            path = cached
        else:
            xbmc.executebuiltin('RunPlugin({0})'.format(
                build_url(ctx.base_url, 'preload_bg', track=track_id)))

    li = track_listitem(track)
    li.setPath(path or url)
    xbmcplugin.setResolvedUrl(ctx.handle, True, li)


def preload_bg(ctx, params):
    """Background cache download (started via RunPlugin, no UI)."""
    track_id = params.get('track') or ''
    if not track_id:
        return
    try:
        url, _track = ctx.service.resolve_stream(track_id)
    except Exception:
        log.info('background preload resolve failed for %s', track_id, exc_info=True)
        return
    audiocache.preload_track(ctx.profile, url, track_id)


def track_placeholder():
    import xbmcgui
    return xbmcgui.ListItem(offscreen=True)
