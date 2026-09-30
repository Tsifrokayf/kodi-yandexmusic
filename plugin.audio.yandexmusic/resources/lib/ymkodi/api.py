"""Yandex Music API service layer: caching, stream resolution, library ops."""
import json
import logging

from yandex_music import (
    ChartInfo,
    GeneratedPlaylist,
    Landing,
    LandingList,
    Playlist,
    Search,
    StationResult,
    Track,
)
from yandex_music.exceptions import UnauthorizedError, YandexMusicError

from .auth import NotAuthorized, get_access_token

log = logging.getLogger(__name__)

BATCH_LIMIT = 100


class StreamError(Exception):
    """Direct audio stream URL could not be obtained."""


def pick_download_info(infos, preferred_codec='mp3'):
    """Pick the best DownloadInfo: preferred codec, highest bitrate, not preview."""
    if not infos:
        return None
    ordered = sorted(
        infos,
        key=lambda item: (
            0 if item.codec == preferred_codec else 1,
            0 if not item.preview else 1,
            -int(item.bitrate_in_kbps or 0),
        ),
    )
    return ordered[0]


def split_track_id(track_id):
    """'123:456' -> ('123', '456'); '123' -> ('123', None)."""
    text = str(track_id)
    if ':' in text:
        track_only, _, album_id = text.partition(':')
        return track_only, album_id or None
    return text, None


def parse_wave_result(result, client):
    """Tracks from POST /rotor/session/new (My Wave) as a list of Track."""
    if not isinstance(result, dict):
        return []
    tracks = []
    for item in result.get('sequence') or ():
        if not isinstance(item, dict):
            continue
        track = Track.de_json(item.get('track'), client)
        if track is not None:
            tracks.append(track)
    return tracks


def extract_playlists(result):
    """Normalize client.playlists() result to a list of Playlist objects."""
    if result is None:
        return []
    if isinstance(result, Playlist):
        return [result]
    items = getattr(result, 'playlists', None)
    if items:
        return list(items)
    try:
        return list(result)
    except TypeError:
        return []


class YandexMusicService(object):
    def __init__(self, store, manual_token=None, codec='mp3', cache=None, cache_ttl=3600):
        self.store = store
        self.manual_token = (manual_token or '').strip() or None
        self.codec = codec or 'mp3'
        self.cache = cache
        self.cache_ttl = max(int(cache_ttl or 60), 1) * 60
        self._client = None

    @property
    def client(self):
        if self._client is None:
            token = get_access_token(self.store, self.manual_token)
            try:
                self._client = self.build_client(token)
            except UnauthorizedError:
                raise NotAuthorized('token rejected by API')
        return self._client

    @staticmethod
    def build_client(token):
        from yandex_music import Client
        return Client(token).init()

    # ------------------------------------------------------------------ cache

    def _cached_call(self, key, ttl, call, restore):
        raw = None
        if self.cache is not None:
            raw = self.cache.get(key, ttl)
        if raw is None:
            try:
                obj = call()
            except UnauthorizedError:
                raise NotAuthorized('token rejected by API')
            except YandexMusicError:
                raise
            if obj is None:
                return None
            try:
                if isinstance(obj, list):
                    raw = [json.loads(item.to_json()) for item in obj]
                else:
                    raw = json.loads(obj.to_json())
            except Exception:
                log.debug('cannot serialize %s for cache', key, exc_info=True)
                return obj
            if self.cache is not None:
                self.cache.set(key, raw)
        return restore(raw)

    # ---------------------------------------------------------------- catalog

    def account_status(self):
        return self.client.account_status()

    def landing(self, blocks):
        key = 'landing:' + ','.join(blocks)
        client = self.client
        return self._cached_call(
            key,
            self.cache_ttl,
            lambda: client.landing(blocks),
            lambda raw: Landing.de_json(raw, client) if raw else None,
        )

    def chart(self):
        client = self.client
        return self._cached_call(
            'chart',
            self.cache_ttl,
            lambda: client.chart(),
            lambda raw: ChartInfo.de_json(raw, client) if raw else None,
        )

    def new_releases(self):
        client = self.client
        return self._cached_call(
            'new_releases',
            self.cache_ttl,
            lambda: client.new_releases(),
            lambda raw: LandingList.de_json(raw, client) if raw else None,
        )

    def new_playlists(self):
        client = self.client
        return self._cached_call(
            'new_playlists',
            self.cache_ttl,
            lambda: client.new_playlists(),
            lambda raw: LandingList.de_json(raw, client) if raw else None,
        )

    def search(self, text, type_='track', page=0):
        client = self.client
        key = 'search:{0}:{1}:{2}'.format(type_, text, page)
        return self._cached_call(
            key,
            max(self.cache_ttl // 4, 300),
            lambda: client.search(text, False, type_, page),
            lambda raw: Search.de_json(raw, client) if raw else None,
        )

    # --------------------------------------------------------------- library

    def my_playlists(self):
        client = self.client
        return self._cached_call(
            'my_playlists',
            300,
            lambda: client.users_playlists_list(),
            lambda raw: [Playlist.de_json(item, client) for item in raw] if raw else [],
        )

    def playlist_by_id(self, uid, kind):
        return self.client.users_playlists(int(kind), int(uid))

    def generated_playlist(self, playlist_id):
        result = self.client.playlists_personal(playlist_id)
        if isinstance(result, GeneratedPlaylist):
            return result.data
        return None

    def likes_tracks_list(self):
        return self.client.users_likes_tracks()

    def likes_track_keys(self, ttl=120):
        """Set of 'trackId:albumId' keys currently liked."""
        key = 'likes_track_keys'
        cached = self.cache.get(key, ttl) if self.cache is not None else None
        if cached is not None:
            return set(cached)
        tracks_list = self.likes_tracks_list()
        keys = []
        if tracks_list is not None:
            keys = [item.track_id for item in tracks_list.tracks]
        if self.cache is not None:
            self.cache.set(key, keys)
        return set(keys)

    def liked_album_ids(self):
        return set(str(item.id) for item in self.client.users_likes_albums())

    def liked_artist_ids(self):
        return set(str(item.id) for item in self.client.users_likes_artists())

    def liked_playlists(self):
        client = self.client
        try:
            likes = client.users_likes_playlists()
        except YandexMusicError:
            return []
        ids = [str(item.id) for item in likes if getattr(item, 'id', None)]
        if not ids:
            return []
        return self.playlists_by_ids(ids)

    def playlists_by_ids(self, ids):
        if not ids:
            return []
        client = self.client
        collected = []
        for index in range(0, len(ids), BATCH_LIMIT):
            chunk = ids[index:index + BATCH_LIMIT]
            try:
                result = client.playlists(chunk)
            except YandexMusicError:
                log.warning('playlist fetch failed', exc_info=True)
                continue
            collected.extend(extract_playlists(result))
        return collected

    def albums(self, album_ids):
        if not album_ids:
            return []
        client = self.client
        collected = []
        for index in range(0, len(album_ids), BATCH_LIMIT):
            chunk = album_ids[index:index + BATCH_LIMIT]
            collected.extend(client.albums(chunk))
        return collected

    def artists(self, artist_ids):
        if not artist_ids:
            return []
        client = self.client
        collected = []
        for index in range(0, len(artist_ids), BATCH_LIMIT):
            chunk = artist_ids[index:index + BATCH_LIMIT]
            collected.extend(client.artists(chunk))
        return collected

    def album_with_tracks(self, album_id):
        return self.client.albums_with_tracks(album_id)

    def artist_brief(self, artist_id):
        return self.client.artists_brief_info(artist_id)

    def artist_albums(self, artist_id, page=0, page_size=25):
        result = self.client.artists_direct_albums(artist_id, page, page_size)
        albums = None
        if result is not None:
            albums = getattr(result, 'albums', None) or getattr(result, 'results', None)
        return list(albums or []), result

    def artist_similar(self, artist_id):
        result = self.client.artists_similar(artist_id, 0, 25)
        artists = None
        if result is not None:
            artists = getattr(result, 'artists', None) or getattr(result, 'results', None)
        return list(artists or [])

    def track(self, track_id):
        tracks = self.client.tracks([track_id])
        if not tracks:
            return None
        return tracks[0]

    # ------------------------------------------------------------- tracks set

    def full_tracks(self, short_items, limit=None):
        """Resolve TrackShort-like items to full Track objects preserving order."""
        if short_items is None:
            return []
        if limit is not None:
            short_items = short_items[:limit]
        items = list(short_items)

        resolved = []
        missing = []
        for item in items:
            track = getattr(item, 'track', None)
            if track is not None:
                resolved.append(track)
            else:
                missing.append(item)

        fetched = {}
        ids = [item.track_id for item in missing]
        for index in range(0, len(ids), BATCH_LIMIT):
            chunk = ids[index:index + BATCH_LIMIT]
            try:
                for track in self.client.tracks(chunk):
                    fetched[track.track_id] = track
                    fetched[str(track.id)] = track
            except YandexMusicError:
                log.warning('batch track fetch failed', exc_info=True)

        result = []
        resolved_iter = iter(resolved)
        for item in items:
            if getattr(item, 'track', None) is not None:
                result.append(next(resolved_iter))
                continue
            track = fetched.get(item.track_id) or fetched.get(split_track_id(item.track_id)[0])
            if track is not None:
                result.append(track)
        return result

    # ----------------------------------------------------------------- likes

    def toggle_like_track(self, track_id):
        liked = self.liked_track_keys()
        if track_id in liked or split_track_id(track_id)[0] in liked:
            self.client.users_likes_tracks_remove([track_id])
            action = 'removed'
        else:
            self.client.users_likes_tracks_add([track_id])
            action = 'added'
        if self.cache is not None:
            self.cache.invalidate('likes_track_keys')
        return action

    def set_track_like(self, track_id, liked):
        if liked:
            self.client.users_likes_tracks_add([track_id])
        else:
            self.client.users_likes_tracks_remove([track_id])
        if self.cache is not None:
            self.cache.invalidate('likes_track_keys')

    def set_album_like(self, album_id, liked):
        if liked:
            self.client.users_likes_albums_add([album_id])
        else:
            self.client.users_likes_albums_remove([album_id])

    def set_artist_like(self, artist_id, liked):
        if liked:
            self.client.users_likes_artists_add([artist_id])
        else:
            self.client.users_likes_artists_remove([artist_id])

    def add_to_playlist(self, uid, kind, track_id):
        track_only, album_id = split_track_id(track_id)
        revision = 1
        try:
            playlist = self.playlist_by_id(uid, kind)
            if playlist is not None and playlist.revision is not None:
                revision = playlist.revision
        except YandexMusicError:
            pass
        return self.client.users_playlists_insert_track(
            int(kind), track_only, album_id or 0, at=0, revision=revision, user_id=int(uid)
        )

    # ----------------------------------------------------------------- radio

    def stations(self):
        client = self.client
        return self._cached_call(
            'stations',
            self.cache_ttl,
            lambda: client.rotor_stations_list(),
            lambda raw: [StationResult.de_json(item, client) for item in raw] if raw else [],
        )

    @staticmethod
    def station_full_id(station_result):
        station = station_result.station
        station_id = getattr(station, 'id', None)
        if station_id is None:
            return None
        return '{0}:{1}'.format(station_id.type, station_id.tag)

    def station_tracks(self, station, queue=None):
        result = self.client.rotor_station_tracks(station, True, queue)
        if result is None:
            return None, []
        tracks = [item.track for item in result.sequence if item.track is not None]
        return result.batch_id, tracks

    def radio_started(self, station, batch_id=None):
        try:
            self.client.rotor_station_feedback_radio_started(station, 'plugin', batch_id=batch_id)
            return True
        except YandexMusicError:
            log.debug('radioStarted feedback failed', exc_info=True)
            return False

    def radio_track_started(self, station, track_id, batch_id=None):
        track_only, _ = split_track_id(track_id)
        try:
            self.client.rotor_station_feedback_track_started(
                station, track_only, batch_id=batch_id
            )
            return True
        except YandexMusicError:
            log.debug('trackStarted feedback failed', exc_info=True)
            return False

    # --------------------------------------------------------------- my wave

    def wave_session(self):
        """Start a My Wave rotor session: POST /rotor/session/new.

        Returns (meta, tracks) where meta carries session/batch ids and
        tracks is a list of yandex_music.Track. Empty tuple on failure.
        """
        client = self.client
        payload = json.dumps({
            'includeTracksInResponse': True,
            'includeWaveModel': True,
            'interactive': True,
            'seeds': [],
        })
        try:
            result = client.request.post(
                '{0}/rotor/session/new'.format(client.base_url),
                data=payload,
            )
        except YandexMusicError:
            log.warning('my wave session failed', exc_info=True)
            return None, []
        if not result:
            return None, []
        tracks = parse_wave_result(result, client)
        meta = {
            'session': result.get('radioSessionId'),
            'batch': result.get('batchId'),
        }
        return meta, tracks

    def track_lyrics(self, track_id, fmt='TEXT'):
        """Lyrics text for a track ('TEXT' plain or 'LRC' timed), or None."""
        plain, _, album_id = str(track_id).partition(':')
        request_id = plain if album_id else track_id
        client = self.client
        try:
            info = client.tracks_lyrics(request_id, fmt)
        except YandexMusicError:
            log.debug('lyrics unavailable for %s', track_id, exc_info=True)
            return None
        if info is None:
            return None
        try:
            return info.fetch_lyrics()
        except YandexMusicError:
            log.debug('lyrics fetch failed for %s', track_id, exc_info=True)
            return None

    # --------------------------------------------------------------- playback

    def resolve_stream(self, track_id):
        """Return (direct_url, Track) for the given 'trackId[:albumId]' id."""
        track = self.track(track_id)
        if track is None:
            raise StreamError('track not found: {0}'.format(track_id))
        try:
            infos = track.get_download_info()
        except YandexMusicError as error:
            raise StreamError('download info failed: {0}'.format(error))
        info = pick_download_info(infos, self.codec)
        if info is None:
            raise StreamError('no download info for {0}'.format(track_id))
        try:
            url = info.get_direct_link()
        except YandexMusicError as error:
            raise StreamError('direct link failed: {0}'.format(error))
        if not url:
            raise StreamError('empty direct link for {0}'.format(track_id))
        return url, track
