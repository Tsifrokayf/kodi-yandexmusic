"""Codec-aware stream resolution via the signed /get-file-info endpoint."""
import json
import unittest
import urllib.error
from unittest import mock

import _bootstrap  # noqa: F401

from ymkodi import api as api_mod
from ymkodi.api import FILE_INFO_CODECS, YandexMusicService, file_info_sign
from ymkodi.audiocache import cached_path


class FakeResponse(object):
    def __init__(self, payload):
        self._data = json.dumps(payload).encode('utf-8')

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeDownloadInfo(object):
    def __init__(self, codec, bitrate):
        self.codec = codec
        self.bitrate_in_kbps = bitrate
        self.preview = False

    def get_direct_link(self):
        return 'http://classic/{0}/{1}'.format(self.codec, self.bitrate_in_kbps)


class FakeTrack(object):
    def __init__(self):
        self.download_calls = 0

    def get_download_info(self):
        self.download_calls += 1
        return [FakeDownloadInfo('mp3', 192), FakeDownloadInfo('mp3', 320)]


def make_service(codec):
    service = YandexMusicService(store=None, codec=codec)
    service.track = lambda track_id: FakeTrack()
    return service


def patch_token():
    return mock.patch.object(api_mod, 'get_access_token',
                             return_value='TOKEN')


class SignTest(unittest.TestCase):
    def test_matches_reference_vector(self):
        # Golden vector from MarshalX/yandex-music-api issue #656.
        sign = file_info_sign(1724399849, '117708948', 'lossless',
                              'flac,aac,he-aac,mp3', 'raw')
        self.assertEqual(sign, 'VLPICid1TFCXy27MK7jSoQE4BCPN4hCJ0BCvu2FauvU')

    def test_commas_are_stripped_from_message(self):
        self.assertEqual(
            file_info_sign(1, '2', 'lossless', 'a,b', 'raw'),
            file_info_sign(1, '2', 'lossless', 'ab', 'raw'))


class CodecParamsTest(unittest.TestCase):
    def test_flac_asks_lossless_with_mp4_variants(self):
        quality, codecs = FILE_INFO_CODECS['flac']
        self.assertEqual(quality, 'lossless')
        self.assertIn('flac-mp4', codecs)

    def test_aac_never_asks_for_flac(self):
        quality, codecs = FILE_INFO_CODECS['aac']
        self.assertEqual(quality, 'hq')
        self.assertNotIn('flac', codecs.split(','))
        self.assertIn('aac-mp4', codecs)


class FileInfoUrlTest(unittest.TestCase):
    def test_mp3_prefers_classic_endpoint(self):
        service = make_service('mp3')
        with patch_token():
            with mock.patch.object(api_mod.urllib.request, 'urlopen') as urlopen:
                self.assertIsNone(service._file_info_url('1:2'))
                urlopen.assert_not_called()

    def test_flac_returns_url_and_plain_track_id(self):
        payload = {'result': {'downloadInfo': {
            'codec': 'flac-mp4', 'bitrate': 0,
            'urls': ['http://flac/track.audio']}}}
        captured = {}

        def fake_urlopen(request, timeout=None):
            captured['url'] = request.full_url
            captured['headers'] = dict(request.header_items())
            return FakeResponse(payload)

        service = make_service('flac')
        with patch_token():
            with mock.patch.object(api_mod.urllib.request, 'urlopen',
                                   side_effect=fake_urlopen):
                self.assertEqual(service._file_info_url('66617665:17889344'),
                                 'http://flac/track.audio')
        self.assertIn('trackId=66617665', captured['url'])
        self.assertNotIn('17889344', captured['url'])
        self.assertIn('quality=lossless', captured['url'])
        self.assertIn('transports=raw', captured['url'])
        self.assertEqual(captured['headers'].get('Authorization'),
                         'OAuth TOKEN')

    def test_encrypted_answer_is_rejected(self):
        payload = {'result': {'downloadInfo': {
            'codec': 'aac-mp4', 'key': 'deadbeef',
            'urls': ['http://crypt/track.audio']}}}
        service = make_service('aac')
        with patch_token():
            with mock.patch.object(api_mod.urllib.request, 'urlopen',
                                   return_value=FakeResponse(payload)):
                self.assertIsNone(service._file_info_url('1:2'))

    def test_list_response_uses_first_entry(self):
        payload = {'result': {'downloadInfo': [
            {'codec': 'aac-mp4', 'urls': ['http://first'],
             'key': None}]}}
        service = make_service('aac')
        with patch_token():
            with mock.patch.object(api_mod.urllib.request, 'urlopen',
                                   return_value=FakeResponse(payload)):
                self.assertEqual(service._file_info_url('1:2'), 'http://first')

    def test_http_error_falls_back_to_none(self):
        service = make_service('flac')
        with patch_token():
            with mock.patch.object(
                    api_mod.urllib.request, 'urlopen',
                    side_effect=urllib.error.URLError('nope')):
                self.assertIsNone(service._file_info_url('1:2'))


class ResolveStreamTest(unittest.TestCase):
    def test_flac_prefers_file_info_without_classic_call(self):
        payload = {'result': {'downloadInfo': {
            'codec': 'flac-mp4', 'urls': ['http://lossless/audio']}}}
        service = make_service('flac')
        track = service.track('1:2')
        service.track = lambda track_id: track
        with patch_token():
            with mock.patch.object(api_mod.urllib.request, 'urlopen',
                                   return_value=FakeResponse(payload)):
                url, _ = service.resolve_stream('1:2')
        self.assertEqual(url, 'http://lossless/audio')
        self.assertEqual(track.download_calls, 0)

    def test_falls_back_to_classic_when_file_info_fails(self):
        service = make_service('flac')
        track = service.track('1:2')
        service.track = lambda track_id: track
        with patch_token():
            with mock.patch.object(
                    api_mod.urllib.request, 'urlopen',
                    side_effect=urllib.error.URLError('nope')):
                url, _ = service.resolve_stream('1:2')
        self.assertEqual(url, 'http://classic/mp3/320')
        self.assertEqual(track.download_calls, 1)

    def test_mp3_uses_classic_endpoint(self):
        service = make_service('mp3')
        track = service.track('1:2')
        service.track = lambda track_id: track
        url, _ = service.resolve_stream('1:2')
        self.assertEqual(url, 'http://classic/mp3/320')


class CacheNameTest(unittest.TestCase):
    def test_codec_suffix_changes_cache_file(self):
        base = cached_path('/tmp/profile', '123:456')
        flac = cached_path('/tmp/profile', '123:456', 'flac')
        aac = cached_path('/tmp/profile', '123:456', 'aac')
        self.assertTrue(base.endswith('123_456.audio'))
        self.assertTrue(flac.endswith('123_456_flac.audio'))
        self.assertTrue(aac.endswith('123_456_aac.audio'))
        self.assertNotEqual(base, flac)


if __name__ == '__main__':
    unittest.main()
