"""Kodi UI helpers: list items, dialogs, notifications."""
import os

import xbmc
import xbmcgui
import xbmcplugin

from .urls import build_url


def sphere_path(addon_path):
    """Path to the animated sphere GIF (used as radio fanart)."""
    path = os.path.join(addon_path, 'resources', 'media', 'sphere.gif')
    return path if os.path.isfile(path) else None


def image_url(uri, size=400):
    if not uri:
        return None
    text = str(uri)
    if text.startswith('//'):
        text = 'https:' + text
    if not text.startswith(('http://', 'https://')):
        text = 'https://' + text
    if '%%' in text:
        return text.replace('%%', '%%?size={0}x{0}'.format(size), 1)
    return text


def object_art(obj, size=600):
    if obj is None:
        return {}
    uri = getattr(obj, 'cover_uri', None)
    if uri is None:
        cover = getattr(obj, 'cover', None)
        uri = getattr(cover, 'uri', None)
    if uri is None:
        uri = getattr(obj, 'og_image', None)
    if isinstance(uri, list):
        uri = uri[0] if uri else None
    if not uri:
        return {}
    url = image_url(uri, size)
    return {'thumb': url, 'icon': url, 'fanart': url}


def track_art(track, size=600):
    art = object_art(track, size)
    if art:
        return art
    albums = getattr(track, 'albums', None) or []
    if albums:
        return object_art(albums[0], size)
    return {}


def track_artists(track):
    artists = getattr(track, 'artists', None) or []
    return ', '.join(artist.name for artist in artists if getattr(artist, 'name', None))


def track_listitem(track, menu=None, extra_art=None):
    title = getattr(track, 'title', None) or ''
    artists = track_artists(track)
    label = title if not artists else '{0} — {1}'.format(artists, title)
    li = xbmcgui.ListItem(label=label, offscreen=True)
    li.setProperty('IsPlayable', 'true')
    info = {'title': title, 'mediatype': 'song'}
    if artists:
        info['artist'] = [a.name for a in (getattr(track, 'artists', None) or [])]
    albums = getattr(track, 'albums', None) or []
    if albums:
        info['album'] = albums[0].title or ''
    duration_ms = getattr(track, 'duration_ms', None)
    if duration_ms:
        info['duration'] = int(duration_ms // 1000)
    li.setInfo('music', info)
    art = track_art(track)
    if extra_art:
        art.update(extra_art)
    if art:
        li.setArt(art)
    if menu:
        li.addContextMenuItems(menu)
    return li


def add_track(ctx, track, play_params=None, menu=None, extra_art=None):
    params = {'track': track.track_id}
    if play_params:
        params.update(play_params)
    url = build_url(ctx.base_url, 'play', **params)
    li = track_listitem(track, menu=menu, extra_art=extra_art)
    xbmcplugin.addDirectoryItem(ctx.handle, url, li, False)


def add_folder(ctx, title, action, params=None, art=None, menu=None):
    url = build_url(ctx.base_url, action, **(params or {}))
    li = xbmcgui.ListItem(label=title, offscreen=True)
    if art:
        li.setArt(art)
    if menu:
        li.addContextMenuItems(menu)
    xbmcplugin.addDirectoryItem(ctx.handle, url, li, True)


def finish(ctx, content='songs'):
    xbmcplugin.setContent(ctx.handle, content)
    xbmcplugin.addSortMethod(ctx.handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(ctx.handle)


def notify(ctx, title, message, icon=None, sound=False):
    if not title:
        title = ctx.addon.getAddonInfo('name')
    if icon is None:
        icon = ctx.addon.getAddonInfo('icon')
    xbmcgui.Dialog().notification(title, message, icon, 4000, sound)


def alert(ctx, title, message):
    xbmcgui.Dialog().ok(title, message)


def ask(ctx, heading, default=''):
    return xbmcgui.Dialog().input(heading, default, xbmcgui.INPUT_ALPHANUM)


def select(ctx, heading, options):
    index = xbmcgui.Dialog().select(heading, options)
    if index is None or index < 0:
        return None
    return index
