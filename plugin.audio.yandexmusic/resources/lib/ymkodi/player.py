"""Playback: resolve direct stream URL and hand it to Kodi."""
import logging

import xbmcplugin

from .api import StreamError
from .auth import NotAuthorized
from .ui import notify, track_listitem

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

    li = track_listitem(track)
    li.setPath(url)
    xbmcplugin.setResolvedUrl(ctx.handle, True, li)


def track_placeholder():
    import xbmcgui
    return xbmcgui.ListItem(offscreen=True)
