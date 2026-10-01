"""Music info tags on track list items (Kodi 21 drops list-valued artist)."""
import unittest

import _bootstrap  # noqa: F401

try:
    import xbmcgui
except ImportError:
    xbmcgui = None

from yandex_music import Track

from ymkodi.ui import track_listitem


def make_track(artists):
    return Track.de_json({'id': 1, 'title': 'Song',
                          'artists': [{'id': i, 'name': name}
                                      for i, name in enumerate(artists, 1)],
                          'albums': [{'id': 9, 'title': 'Album'}],
                          'duration_ms': 1000}, None)


@unittest.skipIf(xbmcgui is None, 'xbmc stubs not available')
class TrackListItemInfoTest(unittest.TestCase):
    def info(self, track):
        return track_listitem(track).info['music']

    def test_artist_is_joined_string(self):
        info = self.info(make_track(['One', 'Two']))
        self.assertIsInstance(info['artist'], str)
        self.assertEqual(info['artist'], 'One, Two')

    def test_single_artist_string(self):
        self.assertEqual(self.info(make_track(['Solo']))['artist'], 'Solo')

    def test_no_artists_no_key(self):
        info = self.info(make_track([]))
        self.assertNotIn('artist', info)

    def test_label_keeps_artist_prefix(self):
        li = track_listitem(make_track(['Solo']))
        self.assertEqual(li.label, 'Solo — Song')

    def test_title_and_album_still_set(self):
        info = self.info(make_track(['Solo']))
        self.assertEqual(info['title'], 'Song')
        self.assertEqual(info['album'], 'Album')


if __name__ == '__main__':
    unittest.main()
