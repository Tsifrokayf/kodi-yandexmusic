"""Tests for the pre-playback track download cache."""
import http.server
import os
import shutil
import tempfile
import threading
import unittest

import _bootstrap  # noqa: F401

from ymkodi import audiocache


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


class AudiocacheTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ymcache-')
        self.payload = os.urandom(300 * 1024)
        src = os.path.join(self.tmp, 'src.bin')
        with open(src, 'wb') as out:
            out.write(self.payload)

        handler = lambda *a, **kw: _QuietHandler(*a, directory=self.tmp, **kw)  # noqa: E731
        self.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

        self.profile = os.path.join(self.tmp, 'profile')
        os.makedirs(self.profile)

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def url(self, name='src.bin'):
        return 'http://127.0.0.1:{0}/{1}'.format(self.port, name)

    def test_fetch_downloads_and_reports_progress(self):
        dest = os.path.join(self.tmp, 'out.bin')
        progress = []
        size = audiocache.fetch(self.url(), dest, on_progress=progress.append)
        self.assertEqual(size, len(self.payload))
        with open(dest, 'rb') as fh:
            self.assertEqual(fh.read(), self.payload)
        self.assertTrue(progress)
        self.assertEqual(progress[-1], 100)
        self.assertFalse(os.path.exists(dest + '.part'))

    def test_preload_caches_then_replays_offline(self):
        first = audiocache.preload_track(self.profile, self.url(), '12:34')
        self.assertTrue(first and os.path.exists(first))
        self.httpd.shutdown()
        self.httpd.server_close()
        second = audiocache.preload_track(self.profile, self.url(), '12:34')
        self.assertEqual(first, second)
        with open(second, 'rb') as fh:
            self.assertEqual(fh.read(), self.payload)

    def test_cancel_returns_none_and_removes_file(self):
        path = audiocache.preload_track(
            self.profile, self.url(), '55:66', should_cancel=lambda: True)
        self.assertIsNone(path)
        self.assertFalse(os.path.exists(
            audiocache.cached_path(self.profile, '55:66')))
        self.assertFalse(os.path.exists(
            audiocache.cached_path(self.profile, '55:66') + '.part'))

    def test_network_failure_returns_none(self):
        path = audiocache.preload_track(
            self.profile, 'http://127.0.0.1:1/missing', '77')
        self.assertIsNone(path)
        self.assertFalse(os.path.exists(
            audiocache.cached_path(self.profile, '77')))

    def test_cached_path_is_filesystem_safe(self):
        path = audiocache.cached_path(self.profile, '146081953:39951582')
        self.assertNotIn(':', os.path.basename(path))
        self.assertTrue(path.startswith(self.profile))

    def test_stale_cache_is_refreshed(self):
        first = audiocache.preload_track(self.profile, self.url(), '99')
        stale = audiocache.cached_path(self.profile, '99')
        with open(stale, 'wb') as out:
            out.write(b'old junk')
        os.utime(stale, (0, 0))
        refreshed = audiocache.preload_track(self.profile, self.url(), '99')
        with open(refreshed, 'rb') as fh:
            self.assertEqual(fh.read(), self.payload)
        self.assertIsNotNone(first)


if __name__ == '__main__':
    unittest.main()
