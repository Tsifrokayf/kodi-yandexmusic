import unittest

import _bootstrap  # noqa: F401

from ymkodi.ui import image_url, track_art


class ImageUrlTest(unittest.TestCase):
    def test_protocol_relative_with_template(self):
        self.assertEqual(
            image_url('//avatars.mds.yandex.net/get-music-content/1/%%', 400),
            'https://avatars.mds.yandex.net/get-music-content/1/400x400',
        )

    def test_template_size_embedded(self):
        self.assertEqual(
            image_url('//avatars.mds.yandex.net/get/%%?size=400x400', 200),
            'https://avatars.mds.yandex.net/get/200x200?size=400x400',
        )

    def test_https_kept(self):
        self.assertEqual(
            image_url('https://example.com/a.png'), 'https://example.com/a.png')

    def test_bare_host_prefixed(self):
        self.assertEqual(image_url('example.com/a.png'),
                         'https://example.com/a.png')

    def test_empty(self):
        self.assertIsNone(image_url(''))
        self.assertIsNone(image_url(None))


class TrackArtTest(unittest.TestCase):
    class FakeCover(object):
        def __init__(self, uri):
            self.uri = uri

    class FakeTrack(object):
        def __init__(self, cover_uri=None, cover=None):
            self.cover_uri = cover_uri
            self.cover = cover
            self.albums = []

    def test_cover_uri_from_track(self):
        art = track_art(self.FakeTrack(
            cover_uri='//avatars.mds.yandex.net/get/%%'))
        self.assertEqual(art['thumb'],
                         'https://avatars.mds.yandex.net/get/600x600')
        self.assertEqual(art['icon'], art['thumb'])
        self.assertEqual(art['fanart'], art['thumb'])

    def test_cover_object_fallback(self):
        art = track_art(self.FakeTrack(
            cover=self.FakeCover('//avatars.mds.yandex.net/get/%%')))
        self.assertTrue(art['thumb'].endswith('/600x600'))

    def test_no_cover(self):
        self.assertEqual(track_art(self.FakeTrack()), {})


if __name__ == '__main__':
    unittest.main()
