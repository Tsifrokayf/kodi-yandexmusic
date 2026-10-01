"""Progressive track loading: head first, background refill afterwards."""
import unittest

import _bootstrap  # noqa: F401

try:
    import xbmc
    import xbmcaddon
    import xbmcplugin
except ImportError:
    xbmc = None
    xbmcaddon = None
    xbmcplugin = None

from yandex_music import Track

from ymkodi.api import short_track_ids, unresolved_count
from ymkodi.router import FAST_TRACKS, _render_tracks


def make_track(num):
    return Track.de_json({'id': num, 'title': 'Song {0}'.format(num),
                          'artists': [{'id': 1, 'name': 'Artist'}],
                          'albums': []}, None)


class Short(object):
    def __init__(self, track_id):
        self.track_id = str(track_id)
        self.track = None


class FakeService(object):
    def __init__(self, cached=None, stored_ok=True):
        self.cached = cached
        self.stored_ok = stored_ok
        self.full_calls = []
        self.store_calls = []

    def full_tracks(self, items, limit=None):
        items = list(items)
        self.full_calls.append((len(items), limit))
        chunk = items if limit is None else items[:limit]
        return [make_track(int(item.track_id)) for item in chunk]

    def cached_full_tracks(self, key, shorts):
        return self.cached

    def store_full_tracks(self, key, shorts, tracks):
        self.store_calls.append((key, len(list(shorts)), len(tracks)))
        return self.stored_ok


class FakeCtx(object):
    base_url = 'plugin://plugin.audio.yandexmusic'
    handle = 42

    def __init__(self, service):
        self.service = service
        self.addon = xbmcaddon.Addon()

    def L(self, string_id):
        return str(string_id)


@unittest.skipIf(xbmc is None or not hasattr(xbmcplugin, '_added'),
                 'xbmc stubs not available')
class UnresolvedCountTest(unittest.TestCase):
    def test_shorts_are_unresolved(self):
        self.assertEqual(unresolved_count([Short(1), Short(2)]), 2)

    def test_full_tracks_are_resolved(self):
        self.assertEqual(unresolved_count([make_track(1), make_track(2)]), 0)

    def test_mixed(self):
        self.assertEqual(unresolved_count([make_track(1), Short(2)]), 1)

    def test_empty(self):
        self.assertEqual(unresolved_count([]), 0)


class ShortTrackIdsTest(unittest.TestCase):
    def test_preserves_order_and_stringifies(self):
        self.assertEqual(short_track_ids([Short(1), Short(2)]), ['1', '2'])

    def test_falls_back_to_id(self):
        class Item(object):
            id = 7
        self.assertEqual(short_track_ids([Item()]), ['7'])


@unittest.skipIf(xbmc is None or not hasattr(xbmcplugin, '_added'),
                 'xbmc stubs not available')
class RenderTracksTest(unittest.TestCase):
    def setUp(self):
        xbmcplugin._added[:] = []
        xbmcplugin._ended[:] = []
        xbmc.BUILTINS[:] = []
        xbmc.INFOLABELS.clear()

    def tearDown(self):
        xbmc.INFOLABELS.clear()

    def labels(self):
        return [label for _, label, _ in xbmcplugin._added]

    def test_empty_list_finishes_with_notice(self):
        _render_tracks(FakeCtx(FakeService()), [], 'likes_tracks', cache_key='likes')
        self.assertEqual(self.labels(), [])
        self.assertEqual(xbmcplugin._ended, [FakeCtx.handle])
        self.assertNotIn('Container.Refresh', xbmc.BUILTINS)

    def test_resolved_list_renders_all_without_background(self):
        service = FakeService()
        _render_tracks(FakeCtx(service), [make_track(1), make_track(2)], 'chart',
                       cache_key='chart')
        self.assertEqual(len(self.labels()), 2)
        self.assertEqual(xbmcplugin._ended, [FakeCtx.handle])
        self.assertEqual(service.store_calls, [])
        self.assertNotIn('Container.Refresh', xbmc.BUILTINS)

    def test_large_unresolved_list_shows_head_then_refills(self):
        service = FakeService()
        shorts = [Short(i) for i in range(1, 101)]
        _render_tracks(FakeCtx(service), shorts, 'likes_tracks',
                       liked_keys=set(s.track_id for s in shorts),
                       cache_key='likes')
        self.assertEqual(len(self.labels()), FAST_TRACKS)
        self.assertEqual(xbmcplugin._ended, [FakeCtx.handle])
        self.assertEqual(service.full_calls, [(100, FAST_TRACKS), (100, None)])
        self.assertEqual(service.store_calls, [('likes', 100, 100)])
        self.assertIn('Container.Refresh', xbmc.BUILTINS)

    def test_cache_hit_renders_everything_without_network(self):
        service = FakeService(cached=[make_track(i) for i in range(1, 51)])
        shorts = [Short(i) for i in range(1, 101)]
        _render_tracks(FakeCtx(service), shorts, 'likes_tracks', cache_key='likes')
        self.assertEqual(len(self.labels()), 50)
        self.assertEqual(service.full_calls, [])
        self.assertEqual(service.store_calls, [])
        self.assertNotIn('Container.Refresh', xbmc.BUILTINS)

    def test_store_failure_never_refreshes(self):
        service = FakeService(stored_ok=False)
        shorts = [Short(i) for i in range(1, 101)]
        _render_tracks(FakeCtx(service), shorts, 'likes_tracks', cache_key='likes')
        self.assertEqual(len(self.labels()), FAST_TRACKS)
        self.assertIn(('likes', 100, 100), service.store_calls)
        self.assertNotIn('Container.Refresh', xbmc.BUILTINS)

    def test_left_folder_skips_refresh(self):
        service = FakeService()
        xbmc.INFOLABELS['Container.FolderPath'] = \
            'plugin://plugin.audio.yandexmusic/?action=my'
        shorts = [Short(i) for i in range(1, 101)]
        _render_tracks(FakeCtx(service), shorts, 'likes_tracks', cache_key='likes')
        self.assertEqual(len(self.labels()), FAST_TRACKS)
        self.assertEqual(service.store_calls, [('likes', 100, 100)])
        self.assertNotIn('Container.Refresh', xbmc.BUILTINS)

    def test_without_cache_key_resolves_synchronously(self):
        service = FakeService()
        shorts = [Short(i) for i in range(1, 101)]
        _render_tracks(FakeCtx(service), shorts, 'station')
        self.assertEqual(len(self.labels()), 100)
        self.assertEqual(service.full_calls, [(100, None)])
        self.assertNotIn('Container.Refresh', xbmc.BUILTINS)

    def test_small_unresolved_list_resolves_in_one_go(self):
        service = FakeService()
        shorts = [Short(i) for i in range(1, 6)]
        _render_tracks(FakeCtx(service), shorts, 'likes_tracks', cache_key='likes')
        self.assertEqual(len(self.labels()), 5)
        self.assertEqual(service.full_calls, [(5, None)])
        self.assertNotIn('Container.Refresh', xbmc.BUILTINS)


if __name__ == '__main__':
    unittest.main()
