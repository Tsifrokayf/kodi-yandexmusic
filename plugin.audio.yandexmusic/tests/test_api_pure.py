import unittest

import _bootstrap  # noqa: F401

from ymkodi.api import pick_download_info, split_track_id, extract_playlists


class FakeDownloadInfo(object):
    def __init__(self, codec, bitrate, preview=False):
        self.codec = codec
        self.bitrate_in_kbps = bitrate
        self.preview = preview


class PickDownloadInfoTest(unittest.TestCase):
    def test_prefers_codec_and_bitrate(self):
        infos = [
            FakeDownloadInfo('aac', 320),
            FakeDownloadInfo('mp3', 192),
            FakeDownloadInfo('mp3', 320),
        ]
        picked = pick_download_info(infos, 'mp3')
        self.assertEqual(picked.codec, 'mp3')
        self.assertEqual(picked.bitrate_in_kbps, 320)

    def test_preferred_missing_falls_back_to_highest_bitrate(self):
        infos = [FakeDownloadInfo('aac', 128), FakeDownloadInfo('flac', 1000)]
        picked = pick_download_info(infos, 'mp3')
        self.assertEqual(picked.bitrate_in_kbps, 1000)

    def test_preview_is_last_resort(self):
        infos = [FakeDownloadInfo('mp3', 96, preview=True), FakeDownloadInfo('mp3', 320, preview=False)]
        self.assertFalse(pick_download_info(infos, 'mp3').preview)

    def test_empty(self):
        self.assertIsNone(pick_download_info([], 'mp3'))
        self.assertIsNone(pick_download_info(None, 'mp3'))


class SplitTrackIdTest(unittest.TestCase):
    def test_with_album(self):
        self.assertEqual(split_track_id('123:456'), ('123', '456'))

    def test_plain(self):
        self.assertEqual(split_track_id('123'), ('123', None))

    def test_empty_album(self):
        self.assertEqual(split_track_id('123:'), ('123', None))

    def test_int(self):
        self.assertEqual(split_track_id(123), ('123', None))


class ExtractPlaylistsTest(unittest.TestCase):
    def test_none(self):
        self.assertEqual(extract_playlists(None), [])

    def test_wrapped(self):
        class P(object):
            pass
        one = P()
        class Wrapper(object):
            playlists = [one]
        self.assertEqual(extract_playlists(Wrapper()), [one])

    def test_bare_list(self):
        self.assertEqual(extract_playlists([1, 2]), [1, 2])


if __name__ == '__main__':
    unittest.main()
