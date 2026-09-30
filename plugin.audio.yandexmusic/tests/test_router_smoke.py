"""Router smoke test using stubbed Kodi modules (set YM_TEST_STUBS)."""
import unittest

import _bootstrap  # noqa: F401

try:
    import xbmcplugin
except ImportError:
    xbmcplugin = None

from ymkodi.urls import parse_params


def render(query):
    from ymkodi.router import run
    xbmcplugin._added.clear()
    run(['plugin://plugin.audio.yandexmusic', '1', query])
    return [(url, li.label, folder) for url, li, folder in xbmcplugin._added]


@unittest.skipIf(xbmcplugin is None or not hasattr(xbmcplugin, '_added'),
                 'xbmc stubs not available')
class RouterSmokeTest(unittest.TestCase):
    def actions(self, query):
        return [parse_params(url.split('?', 1)[1]).get('action') for url, _, _ in render(query)]

    def test_root(self):
        self.assertEqual(self.actions(''),
                         ['player', 'home', 'my', 'search', 'radio', 'wave',
                          'account', 'settings'])

    def test_home(self):
        self.assertEqual(self.actions('?action=home'),
                         ['chart', 'new_releases', 'new_playlists', 'personal'])

    def test_my(self):
        self.assertEqual(self.actions('?action=my'),
                         ['likes_tracks', 'likes_albums', 'likes_artists',
                          'playlists', 'liked_playlists'])

    def test_search(self):
        self.assertEqual(self.actions('?action=search'),
                         ['search_results', 'search_results', 'search_results', 'search_results'])

    def test_account_not_logged_in(self):
        self.assertEqual(self.actions('?action=account'), ['login', 'settings'])

    def test_unauthed_action_falls_back_to_account(self):
        self.assertEqual(self.actions('?action=radio'), ['login', 'settings'])

    def test_unknown_action_falls_back_to_root(self):
        self.assertEqual(self.actions('?action=bogus'),
                         ['player', 'home', 'my', 'search', 'radio', 'wave',
                          'account', 'settings'])

    def test_player_window_opens_visualisation(self):
        import xbmc
        had_music = xbmc.Player.playing
        had_video = xbmc.Player.playing_video
        xbmc.BUILTINS[:] = []
        try:
            xbmc.Player.playing = True
            self.assertEqual(self.actions('?action=player'), ['home'])
            self.assertIn('ActivateWindow(visualisation)', xbmc.BUILTINS)

            xbmc.Player.playing_video = True
            xbmc.BUILTINS[:] = []
            self.actions('?action=player')
            self.assertIn('ActivateWindow(fullscreenvideo)', xbmc.BUILTINS)
        finally:
            xbmc.Player.playing = had_music
            xbmc.Player.playing_video = had_video
            xbmc.BUILTINS[:] = []

    def test_player_window_idle_notifies(self):
        import xbmc
        had_music = xbmc.Player.playing
        xbmc.BUILTINS[:] = []
        try:
            xbmc.Player.playing = False
            self.assertEqual(self.actions('?action=player'), ['home'])
            self.assertEqual(xbmc.BUILTINS, [])
        finally:
            xbmc.Player.playing = had_music
            xbmc.BUILTINS[:] = []


if __name__ == '__main__':
    unittest.main()
