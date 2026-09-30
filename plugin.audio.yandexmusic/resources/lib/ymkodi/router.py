"""Plugin router: actions, directory rendering, entry point."""
import logging
import os

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

from . import auth, karaoke, lyrics as lyrics_mod, player, ui
from .api import YandexMusicService
from .cache import Cache
from .store import SessionStore
from .urls import build_url, parse_params

log = logging.getLogger(__name__)


class Context(object):
    def __init__(self, argv):
        self.base_url = argv[0]
        self.handle = int(argv[1])
        self.params = parse_params(argv[2] if len(argv) > 2 else '')
        self.addon = xbmcaddon.Addon()
        profile = xbmcvfs.translatePath(self.addon.getAddonInfo('profile'))
        if not os.path.isdir(profile):
            try:
                os.makedirs(profile, exist_ok=True)
            except OSError:
                pass
        self.profile = profile
        self.store = SessionStore(os.path.join(profile, 'session.json'))
        self.cache = Cache(os.path.join(profile, 'cache'))
        self._service = None

    def L(self, string_id):
        return self.addon.getLocalizedString(string_id)

    @property
    def service(self):
        if self._service is None:
            manual = self.addon.getSetting('manual_token')
            codec = self.addon.getSetting('preferred_codec') or 'mp3'
            try:
                ttl = int(self.addon.getSetting('cache_ttl') or 60)
            except ValueError:
                ttl = 60
            self._service = YandexMusicService(self.store, manual, codec, self.cache, ttl)
        return self._service


# --------------------------------------------------------------------- helpers

def _finish(ctx, content='files'):
    xbmcplugin.setContent(ctx.handle, content)
    xbmcplugin.addSortMethod(ctx.handle, xbmcplugin.SORT_METHOD_UNSORTED)
    xbmcplugin.endOfDirectory(ctx.handle)


def _ask(ctx, heading_id, default=''):
    return xbmcgui.Dialog().input(ctx.L(heading_id), default, xbmcgui.INPUT_ALPHANUM)


def _empty_notice(ctx):
    ui.notify(ctx, '', ctx.L(30092), sound=False)


def _fmt(ctx, string_id, *args):
    """Localized string with % args, tolerant to missing placeholders."""
    try:
        return ctx.L(string_id) % args
    except (TypeError, ValueError):
        return ctx.L(string_id)


def _liked_track_keys(ctx):
    try:
        return ctx.service.liked_track_keys()
    except Exception:
        log.debug('liked track keys unavailable', exc_info=True)
        return set()


def _liked_album_ids(ctx):
    try:
        return ctx.service.liked_album_ids()
    except Exception:
        log.debug('liked album ids unavailable', exc_info=True)
        return set()


def _liked_artist_ids(ctx):
    try:
        return ctx.service.liked_artist_ids()
    except Exception:
        log.debug('liked artist ids unavailable', exc_info=True)
        return set()


def _track_menu(ctx, track, liked_keys):
    full_id = track.track_id
    plain_id = str(track.id)
    is_liked = full_id in liked_keys or plain_id in liked_keys
    menu = [
        (ctx.L(30081 if is_liked else 30080), build_url(ctx.base_url, 'like', track=full_id)),
        (ctx.L(30082), build_url(ctx.base_url, 'add_to_playlist', track=full_id)),
    ]
    if track.albums:
        menu.append((ctx.L(30085), build_url(ctx.base_url, 'album', id=track.albums[0].id)))
    if track.artists:
        menu.append((ctx.L(30086), build_url(ctx.base_url, 'artist', id=track.artists[0].id)))
    menu.append((ctx.L(30061),
                 build_url(ctx.base_url, 'station', station='track:{0}'.format(track.id))))
    if track.artists:
        menu.append((ctx.L(30062),
                     build_url(ctx.base_url, 'station', station='artist:{0}'.format(track.artists[0].id))))
    menu.append((ctx.L(30104), build_url(ctx.base_url, 'lyrics', track=full_id)))
    menu.append((ctx.L(30105), build_url(ctx.base_url, 'karaoke', track=full_id)))
    return menu


def _add_tracks(ctx, tracks, liked_keys, play_params=None, extra_art=None):
    for track in tracks:
        ui.add_track(ctx, track, play_params=play_params,
                     menu=_track_menu(ctx, track, liked_keys), extra_art=extra_art)


def _album_label(album):
    title = album.title or ''
    artists = ', '.join(a.name for a in (album.artists or []) if a.name)
    return '{0} — {1}'.format(artists, title) if artists else title


def _add_albums(ctx, albums, liked_ids):
    for album in albums:
        is_liked = str(album.id) in liked_ids
        menu = [(ctx.L(30081 if is_liked else 30080),
                 build_url(ctx.base_url, 'like_album', id=album.id, liked='0' if is_liked else '1'))]
        if album.artists:
            menu.append((ctx.L(30086), build_url(ctx.base_url, 'artist', id=album.artists[0].id)))
        ui.add_folder(ctx, _album_label(album), 'album', {'id': album.id},
                      art=ui.object_art(album), menu=menu)


def _add_artists(ctx, artists, liked_ids):
    for artist in artists:
        is_liked = str(artist.id) in liked_ids
        menu = [
            (ctx.L(30081 if is_liked else 30080),
             build_url(ctx.base_url, 'like_artist', id=artist.id, liked='0' if is_liked else '1')),
            (ctx.L(30062), build_url(ctx.base_url, 'station', station='artist:{0}'.format(artist.id))),
        ]
        ui.add_folder(ctx, artist.name or '', 'artist', {'id': artist.id},
                      art=ui.object_art(artist), menu=menu)


def _add_playlists(ctx, playlists):
    for playlist_obj in playlists:
        if playlist_obj is None or playlist_obj.uid is None:
            continue
        title = playlist_obj.title or ''
        count = getattr(playlist_obj, 'track_count', None)
        label = '{0} ({1})'.format(title, count) if count else title
        ui.add_folder(ctx, label, 'playlist', {'uid': playlist_obj.uid, 'kind': playlist_obj.kind},
                      art=ui.object_art(playlist_obj))


def _next_page_item(ctx, action, params, page, total, per_page):
    if per_page and total and (page + 1) * per_page < total:
        next_params = dict(params)
        next_params['page'] = str(page + 1)
        ui.add_folder(ctx, ctx.L(30093), action, next_params)


# ------------------------------------------------------------------- handlers

def root(ctx, params):
    ui.add_folder(ctx, ctx.L(30098), 'player')
    ui.add_folder(ctx, ctx.L(30001), 'home')
    ui.add_folder(ctx, ctx.L(30002), 'my')
    ui.add_folder(ctx, ctx.L(30003), 'search')
    ui.add_folder(ctx, ctx.L(30004), 'radio')
    ui.add_folder(ctx, ctx.L(30103), 'wave')
    ui.add_folder(ctx, ctx.L(30005), 'account')
    ui.add_folder(ctx, ctx.L(30006), 'settings')
    _finish(ctx)


def player_window(ctx, params):
    """Quick jump to the full-screen player (visualisation / fullscreen video)."""
    try:
        current = xbmc.Player()
        if current.isPlayingVideo():
            xbmc.executebuiltin('ActivateWindow(fullscreenvideo)')
        elif current.isPlayingAudio():
            xbmc.executebuiltin('ActivateWindow(visualisation)')
        else:
            ui.notify(ctx, '', ctx.L(30099), sound=False)
    except Exception:
        log.exception('cannot open player window')
    # fallback items so closing the player never lands on an empty folder
    state = player.read_play_state(ctx)
    if state and state.get('track'):
        ui.add_folder(ctx, ctx.L(30104), 'lyrics', {'track': state['track']})
        ui.add_folder(ctx, ctx.L(30105), 'karaoke', {'track': state['track']})
    ui.add_folder(ctx, ctx.L(30001), 'home')
    _finish(ctx)


def home(ctx, params):
    ui.add_folder(ctx, ctx.L(30040), 'chart')
    ui.add_folder(ctx, ctx.L(30041), 'new_releases')
    ui.add_folder(ctx, ctx.L(30042), 'new_playlists')
    ui.add_folder(ctx, ctx.L(30043), 'personal')
    _finish(ctx)


def chart(ctx, params):
    info = ctx.service.chart()
    if info is None or info.chart is None:
        _empty_notice(ctx)
        _finish(ctx)
        return
    tracks = ctx.service.full_tracks(info.chart.fetch_tracks())
    if not tracks:
        _empty_notice(ctx)
    _add_tracks(ctx, tracks, _liked_track_keys(ctx))
    _finish(ctx, 'songs')


def new_releases(ctx, params):
    landing = ctx.service.new_releases()
    albums = ctx.service.albums(list(landing.new_releases) if landing else [])
    if not albums:
        _empty_notice(ctx)
    _add_albums(ctx, albums, _liked_album_ids(ctx))
    _finish(ctx, 'albums')


def new_playlists(ctx, params):
    landing = ctx.service.new_playlists()
    playlist_ids = list(landing.new_playlists) if landing else []
    ids = ['{0}:{1}'.format(item.uid, item.kind) for item in playlist_ids]
    playlists = ctx.service.playlists_by_ids(ids)
    if not playlists:
        _empty_notice(ctx)
    _add_playlists(ctx, playlists)
    _finish(ctx, 'albums')


def personal(ctx, params):
    landing = ctx.service.landing(['personalplaylists'])
    playlists = []
    if landing is not None:
        for block in landing.blocks or []:
            for entity in block.entities or []:
                playlist = getattr(entity.data, 'data', None)
                if playlist is not None and playlist.uid is not None:
                    playlists.append(playlist)
    if not playlists:
        _empty_notice(ctx)
    _add_playlists(ctx, playlists)
    _finish(ctx, 'albums')


def my(ctx, params):
    ui.add_folder(ctx, ctx.L(30030), 'likes_tracks')
    ui.add_folder(ctx, ctx.L(30032), 'likes_albums')
    ui.add_folder(ctx, ctx.L(30033), 'likes_artists')
    ui.add_folder(ctx, ctx.L(30035), 'playlists')
    ui.add_folder(ctx, ctx.L(30036), 'liked_playlists')
    _finish(ctx)


def likes_tracks(ctx, params):
    tracks_list = ctx.service.likes_tracks_list()
    tracks = ctx.service.full_tracks(tracks_list.tracks if tracks_list else [])
    if not tracks:
        _empty_notice(ctx)
    _add_tracks(ctx, tracks, _liked_track_keys(ctx))
    _finish(ctx, 'songs')


def likes_albums(ctx, params):
    likes = ctx.service.client.users_likes_albums()
    albums = [like.album for like in likes if getattr(like, 'album', None) is not None]
    if not albums:
        _empty_notice(ctx)
    _add_albums(ctx, albums, _liked_album_ids(ctx))
    _finish(ctx, 'albums')


def likes_artists(ctx, params):
    likes = ctx.service.client.users_likes_artists()
    artists = [like.artist for like in likes if getattr(like, 'artist', None) is not None]
    if not artists:
        _empty_notice(ctx)
    _add_artists(ctx, artists, _liked_artist_ids(ctx))
    _finish(ctx, 'artists')


def playlists(ctx, params):
    playlists_list = ctx.service.my_playlists()
    if not playlists_list:
        _empty_notice(ctx)
    _add_playlists(ctx, playlists_list)
    _finish(ctx, 'albums')


def liked_playlists(ctx, params):
    playlists_list = ctx.service.liked_playlists()
    if not playlists_list:
        _empty_notice(ctx)
    _add_playlists(ctx, playlists_list)
    _finish(ctx, 'albums')


def playlist(ctx, params):
    playlist_obj = ctx.service.playlist_by_id(params.get('uid'), params.get('kind'))
    if playlist_obj is None:
        _empty_notice(ctx)
        _finish(ctx)
        return
    tracks = ctx.service.full_tracks(playlist_obj.fetch_tracks())
    if not tracks:
        _empty_notice(ctx)
    _add_tracks(ctx, tracks, _liked_track_keys(ctx))
    _finish(ctx, 'songs')


def album(ctx, params):
    album_obj = ctx.service.album_with_tracks(params.get('id'))
    if album_obj is None:
        _empty_notice(ctx)
        _finish(ctx)
        return
    tracks = []
    for volume in album_obj.volumes or []:
        tracks.extend(volume)
    if not tracks:
        _empty_notice(ctx)
    _add_tracks(ctx, tracks, _liked_track_keys(ctx))
    _finish(ctx, 'songs')


def artist(ctx, params):
    brief = ctx.service.artist_brief(params.get('id'))
    if brief is None or brief.artist is None:
        _empty_notice(ctx)
        _finish(ctx)
        return
    artist_obj = brief.artist
    menu = [(ctx.L(30062),
             build_url(ctx.base_url, 'station', station='artist:{0}'.format(artist_obj.id)))]
    ui.add_folder(ctx, ctx.L(30051), 'artist_albums', {'id': artist_obj.id}, menu=menu)
    ui.add_folder(ctx, ctx.L(30052), 'artist_similar', {'id': artist_obj.id}, menu=menu)
    popular = brief.popular_tracks or []
    if not popular:
        _empty_notice(ctx)
    _add_tracks(ctx, popular, _liked_track_keys(ctx))
    _finish(ctx, 'songs')


def artist_albums(ctx, params):
    page = int(params.get('page') or 0)
    albums, result = ctx.service.artist_albums(params.get('id'), page)
    if not albums:
        _empty_notice(ctx)
    _add_albums(ctx, albums, _liked_album_ids(ctx))
    pager = getattr(result, 'pager', None)
    if pager is not None:
        _next_page_item(ctx, 'artist_albums',
                        {'id': params.get('id')}, page, pager.total, pager.per_page)
    _finish(ctx, 'albums')


def artist_similar(ctx, params):
    artists = ctx.service.artist_similar(params.get('id'))
    if not artists:
        _empty_notice(ctx)
    _add_artists(ctx, artists, _liked_artist_ids(ctx))
    _finish(ctx, 'artists')


def search(ctx, params):
    ui.add_folder(ctx, ctx.L(30070), 'search_results', {'type': 'track'})
    ui.add_folder(ctx, ctx.L(30071), 'search_results', {'type': 'album'})
    ui.add_folder(ctx, ctx.L(30072), 'search_results', {'type': 'artist'})
    ui.add_folder(ctx, ctx.L(30073), 'search_results', {'type': 'playlist'})
    _finish(ctx)


def search_results(ctx, params):
    type_ = params.get('type') or 'track'
    page = int(params.get('page') or 0)
    query = params.get('q') or _ask(ctx, 30074)
    if not query:
        _finish(ctx)
        return
    result = ctx.service.search(query, type_, page)
    block = None
    if result is not None:
        block = {'track': result.tracks, 'album': result.albums,
                 'artist': result.artists, 'playlist': result.playlists}.get(type_)
    items = list(block.results) if block is not None else []
    content = {'track': 'songs', 'album': 'albums',
               'artist': 'artists'}.get(type_, 'files')
    if not items:
        _empty_notice(ctx)
        _finish(ctx, content)
        return
    common = {'type': type_, 'q': query}
    if type_ == 'track':
        _add_tracks(ctx, items, _liked_track_keys(ctx))
        ui.add_folder(ctx, ctx.L(30094), 'search_results', dict(common, page=''))
    elif type_ == 'album':
        _add_albums(ctx, items, _liked_album_ids(ctx))
    elif type_ == 'artist':
        _add_artists(ctx, items, _liked_artist_ids(ctx))
    else:
        _add_playlists(ctx, items)
    _next_page_item(ctx, 'search_results', dict(common, page=str(page)), page,
                    block.total, block.per_page)
    _finish(ctx, content)


def radio(ctx, params):
    stations = ctx.service.stations()
    sphere = ui.sphere_path(ctx.addon.getAddonInfo('path'))
    count = 0
    for station_result in stations:
        station = station_result.station
        if station is None:
            continue
        full_id = ctx.service.station_full_id(station_result)
        if not full_id:
            continue
        art = {}
        if station.icon is not None and getattr(station.icon, 'image_url', None):
            art['thumb'] = ui.image_url(station.icon.image_url, 400)
        if sphere:
            art['fanart'] = sphere
        ui.add_folder(ctx, station.name or full_id, 'station',
                      {'station': full_id, 'name': station.name or ''}, art=art)
        count += 1
    if not count:
        _empty_notice(ctx)
    _finish(ctx)


def station(ctx, params):
    station_id = params.get('station')
    name = params.get('name') or ''
    batch_id, tracks = ctx.service.station_tracks(station_id)
    if not tracks:
        _empty_notice(ctx)
        _finish(ctx)
        return
    ctx.service.radio_started(station_id, batch_id=batch_id)
    sphere = ui.sphere_path(ctx.addon.getAddonInfo('path'))
    _add_tracks(ctx, tracks, _liked_track_keys(ctx),
                play_params={'station': station_id, 'batch': batch_id},
                extra_art={'fanart': sphere} if sphere else None)
    ui.add_folder(ctx, ctx.L(30095), 'station', {'station': station_id, 'name': name})
    _finish(ctx, 'songs')


def play(ctx, params):
    player.play(ctx, params)


def wave(ctx, params):
    _meta, tracks = ctx.service.wave_session()
    if not tracks:
        _empty_notice(ctx)
        _finish(ctx)
        return
    _add_tracks(ctx, tracks, _liked_track_keys(ctx))
    ui.add_folder(ctx, ctx.L(30095), 'wave')
    _finish(ctx, 'songs')


def lyrics(ctx, params):
    track_id = params.get('track') or ''
    if not track_id:
        return
    text = ctx.service.track_lyrics(track_id, 'TEXT')
    if not text:
        lrc = ctx.service.track_lyrics(track_id, 'LRC')
        text = lyrics_mod.plain_from_lrc(lrc) if lrc else ''
    if not text:
        ui.notify(ctx, '', ctx.L(30106), sound=False)
        return
    xbmcgui.Dialog().textviewer(ctx.L(30104), text)


def karaoke_view(ctx, params):
    state = player.read_play_state(ctx) or {}
    track_id = params.get('track') or state.get('track') or ''
    if not track_id:
        ui.notify(ctx, '', ctx.L(30107), sound=False)
        return
    lrc = ctx.service.track_lyrics(track_id, 'LRC')
    entries = lyrics_mod.parse_lrc(lrc) if lrc else []
    if not entries:
        text = ctx.service.track_lyrics(track_id, 'TEXT')
        if text:
            xbmcgui.Dialog().textviewer(ctx.L(30104), text)
        else:
            ui.notify(ctx, '', ctx.L(30106), sound=False)
        return
    media = xbmc.Player()
    if not media.isPlaying():
        xbmc.executebuiltin('PlayMedia({0})'.format(
            build_url(ctx.base_url, 'play', track=track_id)))
        monitor = xbmc.Monitor()
        for _attempt in range(24):
            if monitor.waitForAbort(0.25) or media.isPlaying():
                break
        if not media.isPlaying():
            ui.notify(ctx, '', ctx.L(30107), sound=False)
            return
    title = ''
    if state.get('track') == track_id:
        artists = state.get('artists') or ''
        track_title = state.get('title') or ''
        title = '{0} — {1}'.format(artists, track_title) if artists else track_title
    overlay = karaoke.KaraokeOverlay(title, entries, ctx.L(30108))
    overlay.run(xbmc.Monitor(), media)


def like(ctx, params):
    track_id = params.get('track')
    action = ctx.service.toggle_like_track(track_id)
    ui.notify(ctx, '', ctx.L(30081 if action == 'removed' else 30080), sound=False)
    xbmc.executebuiltin('Container.Refresh')


def like_album(ctx, params):
    liked = params.get('liked') == '1'
    ctx.service.set_album_like(params.get('id'), liked)
    ui.notify(ctx, '', ctx.L(30081 if liked else 30080), sound=False)
    xbmc.executebuiltin('Container.Refresh')


def like_artist(ctx, params):
    liked = params.get('liked') == '1'
    ctx.service.set_artist_like(params.get('id'), liked)
    ui.notify(ctx, '', ctx.L(30081 if liked else 30080), sound=False)
    xbmc.executebuiltin('Container.Refresh')


def add_to_playlist(ctx, params):
    track_id = params.get('track')
    playlists_list = ctx.service.my_playlists()
    if not playlists_list:
        _empty_notice(ctx)
        return
    index = xbmcgui.Dialog().select(ctx.L(30084), [p.title or '' for p in playlists_list])
    if index is None or index < 0:
        return
    playlist_obj = playlists_list[index]
    ctx.service.add_to_playlist(playlist_obj.uid, playlist_obj.kind, track_id)
    ui.notify(ctx, ctx.L(30083), playlist_obj.title or '', sound=False)


def login(ctx, params):
    progress = {'dialog': None}

    def show_code(code):
        dialog = xbmcgui.DialogProgress()
        try:
            line = ctx.L(30011) % (code.verification_url, code.user_code)
        except (TypeError, ValueError):
            line = '{0}\n{1}'.format(code.verification_url, code.user_code)
        dialog.create(ctx.L(30010), '{0}\n{1}'.format(line, ctx.L(30012)))
        progress['dialog'] = dialog

    def should_cancel():
        dialog = progress.get('dialog')
        if dialog is None:
            return False
        try:
            return dialog.iscanceled()
        except RuntimeError:
            return False

    try:
        auth.device_login(ctx.store, show_code=show_code, should_cancel=should_cancel)
    except auth.AuthError as error:
        if str(error) == 'cancelled':
            ui.notify(ctx, '', ctx.L(30014), sound=False)
        else:
            ui.notify(ctx, ctx.L(30015), str(error), sound=False)
    else:
        ui.notify(ctx, '', ctx.L(30013), sound=False)
    finally:
        dialog = progress.get('dialog')
        if dialog is not None:
            try:
                dialog.close()
            except RuntimeError:
                pass
    # render the account page in place of the login action
    account(ctx, params)


def logout(ctx, params):
    if not xbmcgui.Dialog().yesno(ctx.L(30016), ctx.L(30017)):
        account(ctx, params)
        return
    ctx.store.clear()
    ctx.cache.clear()
    ui.notify(ctx, '', ctx.L(30018), sound=False)
    account(ctx, params)


def account(ctx, params):
    logged = ctx.store.has_token() or bool(ctx.addon.getSetting('manual_token'))
    if not logged:
        ui.add_folder(ctx, ctx.L(30022), 'login')
        ui.add_folder(ctx, ctx.L(30006), 'settings')
        _finish(ctx)
        return
    ui.add_folder(ctx, _fmt(ctx, 30020, '?'), 'account_info')
    ui.add_folder(ctx, ctx.L(30016), 'logout')
    ui.add_folder(ctx, ctx.L(30006), 'settings')
    _finish(ctx)


def account_info(ctx, params):
    try:
        status = ctx.service.account_status()
    except auth.NotAuthorized:
        raise
    except Exception as error:
        log.warning('account_status failed: %s', error)
        status = None
    login_name = '?'
    plus = ctx.L(30097)
    if status is not None:
        if status.account is not None and status.account.login:
            login_name = status.account.login
        if status.plus is not None and status.plus.has_plus:
            plus = ctx.L(30096)
    xbmcgui.Dialog().ok(
        ctx.L(30005),
        '{0}\n{1}'.format(_fmt(ctx, 30020, login_name), _fmt(ctx, 30021, plus)),
    )
    account(ctx, params)


def settings(ctx, params):
    xbmc.executebuiltin('Addon.OpenSettings({0})'.format(ctx.addon.getAddonInfo('id')))
    _finish(ctx)


ACTIONS = {
    'root': root,
    'player': player_window,
    'home': home,
    'chart': chart,
    'new_releases': new_releases,
    'new_playlists': new_playlists,
    'personal': personal,
    'my': my,
    'likes_tracks': likes_tracks,
    'likes_albums': likes_albums,
    'likes_artists': likes_artists,
    'playlists': playlists,
    'liked_playlists': liked_playlists,
    'playlist': playlist,
    'album': album,
    'artist': artist,
    'artist_albums': artist_albums,
    'artist_similar': artist_similar,
    'search': search,
    'search_results': search_results,
    'radio': radio,
    'station': station,
    'play': play,
    'preload_bg': player.preload_bg,
    'wave': wave,
    'lyrics': lyrics,
    'karaoke': karaoke_view,
    'like': like,
    'like_album': like_album,
    'like_artist': like_artist,
    'add_to_playlist': add_to_playlist,
    'login': login,
    'logout': logout,
    'account': account,
    'account_info': account_info,
    'settings': settings,
}


def run(argv):
    ctx = Context(argv)
    action = ctx.params.get('action') or 'root'
    handler = ACTIONS.get(action, root)
    try:
        handler(ctx, ctx.params)
    except auth.NotAuthorized:
        ui.notify(ctx, '', ctx.L(30019), sound=False)
        if action == 'play':
            xbmcplugin.setResolvedUrl(ctx.handle, False, xbmcgui.ListItem(offscreen=True))
            return
        try:
            account(ctx, ctx.params)
        except Exception:
            log.exception('account render after NotAuthorized failed')
            _finish(ctx)
    except Exception as error:
        log.exception('action %s failed', action)
        ui.notify(ctx, ctx.L(30090), str(error), sound=False)
        try:
            _finish(ctx)
        except Exception:
            log.exception('endOfDirectory failed')
