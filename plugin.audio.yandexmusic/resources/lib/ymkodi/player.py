"""Playback: resolve direct stream URL and hand it to Kodi."""
import logging

import xbmcplugin

from . import audiocache
from .api import StreamError
from .auth import NotAuthorized
from .ui import notify, track_artists, track_listitem

log = logging.getLogger(__name__)


def play(ctx, params):
    track_id = params.get('track') or ''
    station = params.get('station')
    batch_id = params.get('batch')

    try:
        url, track = ctx.service.resolve_stream(track_id)
        if station:
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
    if not station and ctx.addon.getSetting('preload_track') != 'false':
        path = _preload_with_dialog(ctx, url, track_id, track)

    li = track_listitem(track)
    li.setPath(path or url)
    xbmcplugin.setResolvedUrl(ctx.handle, True, li)


def _preload_with_dialog(ctx, url, track_id, track):
    import xbmcgui
    title = getattr(track, 'title', None) or track_id
    artists = track_artists(track)
    label = '{0} — {1}'.format(artists, title) if artists else title
    dialog = xbmcgui.DialogProgress()
    dialog.create(ctx.L(30101), label)
    try:
        return audiocache.preload_track(
            ctx.profile, url, track_id,
            on_progress=lambda percent: dialog.update(percent),
            should_cancel=lambda: dialog.iscanceled())
    finally:
        dialog.close()


def track_placeholder():
    import xbmcgui
    return xbmcgui.ListItem(offscreen=True)
