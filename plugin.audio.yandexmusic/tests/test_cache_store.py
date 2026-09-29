import os
import tempfile
import time
import unittest

import _bootstrap  # noqa: F401

from ymkodi.cache import Cache
from ymkodi.store import SessionStore


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='ymcache-')
        self.cache = Cache(self.dir)

    def test_miss_then_hit(self):
        self.assertIsNone(self.cache.get('k', 60))
        self.cache.set('k', {'a': 1})
        self.assertEqual(self.cache.get('k', 60), {'a': 1})

    def test_ttl_expiry(self):
        self.cache.set('k', 'v')
        self.assertIsNone(self.cache.get('k', -1))

    def test_invalidates(self):
        self.cache.set('k', 'v')
        self.cache.invalidate('k')
        self.assertIsNone(self.cache.get('k', 60))
        self.cache.invalidate('missing')  # no raise

    def test_clear(self):
        self.cache.set('a', 1)
        self.cache.set('b', 2)
        self.cache.clear()
        self.assertIsNone(self.cache.get('a', 60))
        self.assertIsNone(self.cache.get('b', 60))

    def test_unsafe_key_is_sanitized(self):
        self.cache.set('../../etc/passwd', 'x')
        found = [n for n in os.listdir(self.dir) if n.endswith('.json')]
        self.assertEqual(len(found), 1)
        self.assertNotIn('/', found[0])
        self.assertNotIn('..', found[0])
        self.assertEqual(self.cache.get('../../etc/passwd', 60), 'x')


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix='ymstore-')
        self.store = SessionStore(os.path.join(self.dir, 'session.json'))

    def test_empty(self):
        self.assertEqual(self.store.load(), {})
        self.assertFalse(self.store.has_token())
        self.assertTrue(self.store.expired())

    def test_save_and_load(self):
        self.store.save('access', 'refresh', 3600)
        self.assertTrue(self.store.has_token())
        data = self.store.load()
        self.assertEqual(data['access_token'], 'access')
        self.assertEqual(data['refresh_token'], 'refresh')

    def test_expiry(self):
        self.store.save('access', None, 100)
        self.assertFalse(self.store.expired(margin=0))
        # simulate old token
        data = self.store.load()
        data['obtained_at'] = time.time() - 1000
        import json
        with open(self.store.path, 'w', encoding='utf-8') as handle:
            json.dump(data, handle)
        self.assertTrue(self.store.expired())

    def test_no_expiry_field_means_valid(self):
        self.store.save('access', None, None)
        self.assertFalse(self.store.expired())

    def test_clear(self):
        self.store.save('access')
        self.store.clear()
        self.assertFalse(self.store.has_token())
        self.store.clear()  # idempotent


if __name__ == '__main__':
    unittest.main()
