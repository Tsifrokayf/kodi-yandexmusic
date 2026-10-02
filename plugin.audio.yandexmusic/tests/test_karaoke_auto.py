"""Karaoke lyrics overlay: auto trigger, plain-text scroll, action merge."""
import unittest
from unittest import mock

import _bootstrap  # noqa: F401

import xbmc
from ymkodi import karaoke as karaoke_mod
from ymkodi import router
from ymkodi.lyrics import spread_entries

LRC = '[00:01.00]line one\n[00:05.50]line two'
TEXT = 'alpha\nbeta\ngamma'


class FakeAddon(object):
    def __init__(self, settings=None):
        self.settings = dict(settings or {})

    def getSetting(self, key):
        return self.settings.get(key, '')


class FakeService(object):
    def __init__(self, lrc=None, text=None):
        self.lrc = lrc
        self.text = text

    def track_lyrics(self, track_id, fmt):
        return self.lrc if fmt == 'LRC' else self.text


class FakeCtx(object):
    def __init__(self, service=None, settings=None, handle=-1):
        self.service = service or FakeService()
        self.addon = FakeAddon(settings)
        self.handle = handle
        self.base_url = 'plugin://plugin.audio.yandexmusic'

    def L(self, key):
        return str(key)


class SpreadEntriesTest(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(spread_entries([], 100), [])
        self.assertEqual(spread_entries(None, 100), [])

    def test_even_distribution_over_duration(self):
        entries = spread_entries(['a', 'b', 'c', 'd'], 40.0)
        self.assertEqual([moment for moment, _ in entries], [0.0, 10.0, 20.0, 30.0])
        self.assertEqual([line for _, line in entries], ['a', 'b', 'c', 'd'])

    def test_blank_lines_skipped(self):
        entries = spread_entries(['a', '  ', 'b'], 30.0)
        self.assertEqual(len(entries), 2)

    def test_unknown_duration_falls_back_to_reading_speed(self):
        entries = spread_entries(['a', 'b'], 0)
        self.assertEqual([moment for moment, _ in entries], [0.0, 3.0])


class KaraokeAutoTest(unittest.TestCase):
    def setUp(self):
        xbmc.Player.playing = True
        for cond in karaoke_mod.FULLSCREEN_CONDITIONS:
            xbmc.COND_VISIBILITY[cond] = True
        self.created = []

        class FakeOverlay(object):
            def __init__(self, title, entries, hint):
                self.created.append(('init', title, list(entries), hint))

            def run(self, monitor, player, require_fullscreen=False):
                self.created.append(('run', require_fullscreen))

        FakeOverlay.created = self.created
        patcher = mock.patch.object(karaoke_mod, 'KaraokeOverlay', FakeOverlay)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        xbmc.Player.playing = False
        xbmc.COND_VISIBILITY.clear()

    def test_setting_off_skips_overlay(self):
        ctx = FakeCtx(service=FakeService(lrc=LRC),
                      settings={'karaoke_auto': 'false'})
        router.karaoke_auto(ctx, {'track': '1:2', 'title': 'A - B'})
        self.assertEqual(self.created, [])

    def test_no_lyrics_skips_overlay(self):
        ctx = FakeCtx(service=FakeService(), settings={'karaoke_auto': 'true'})
        router.karaoke_auto(ctx, {'track': '1:2', 'title': 'A - B'})
        self.assertEqual(self.created, [])

    def test_no_playback_skips_overlay(self):
        xbmc.Player.playing = False
        ctx = FakeCtx(service=FakeService(lrc=LRC),
                      settings={'karaoke_auto': 'true'})
        router.karaoke_auto(ctx, {'track': '1:2', 'title': 'A - B'})
        self.assertEqual(self.created, [])

    def test_not_fullscreen_skips_overlay(self):
        xbmc.COND_VISIBILITY.clear()
        ctx = FakeCtx(service=FakeService(lrc=LRC),
                      settings={'karaoke_auto': 'true'})
        router.karaoke_auto(ctx, {'track': '1:2', 'title': 'A - B'})
        self.assertEqual(self.created, [])

    def test_lrc_shows_overlay_with_title(self):
        ctx = FakeCtx(service=FakeService(lrc=LRC),
                      settings={'karaoke_auto': 'true'})
        router.karaoke_auto(ctx, {'track': '1:2', 'title': 'Artist - Song'})
        kinds = [item[0] for item in self.created]
        self.assertEqual(kinds, ['init', 'run'])
        self.assertTrue(self.created[1][1])  # require_fullscreen
        _, title, entries, _ = self.created[0]
        self.assertEqual(title, 'Artist - Song')
        self.assertEqual(len(entries), 2)

    def test_plain_text_is_spread_for_scroll(self):
        ctx = FakeCtx(service=FakeService(text=TEXT),
                      settings={'karaoke_auto': 'true'})
        router.karaoke_auto(ctx, {'track': '1:2', 'title': ''})
        _, _title, entries, _hint = self.created[0]
        self.assertEqual([line for _, line in entries],
                         ['alpha', 'beta', 'gamma'])


class LyricsActionTest(unittest.TestCase):
    def test_lyrics_action_opens_karaoke_view(self):
        ctx = FakeCtx()
        with mock.patch.object(router, 'karaoke_view') as view:
            router.lyrics(ctx, {'track': '1:2'})
        view.assert_called_once_with(ctx, {'track': '1:2'})


if __name__ == '__main__':
    unittest.main()
