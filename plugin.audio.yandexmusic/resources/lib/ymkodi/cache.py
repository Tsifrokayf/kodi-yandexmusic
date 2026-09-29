"""File-based JSON cache with TTL (pure, testable)."""
import json
import os
import time


class Cache(object):
    def __init__(self, directory):
        self.directory = directory
        try:
            os.makedirs(directory, exist_ok=True)
        except OSError:
            pass

    def _path(self, key):
        safe = ''.join(c if c.isalnum() or c in '-_' else '_' for c in str(key))
        safe = safe.strip('_') or 'entry'
        return os.path.join(self.directory, safe[:160] + '.json')

    def get(self, key, max_age):
        try:
            with open(self._path(key), 'r', encoding='utf-8') as handle:
                payload = json.load(handle)
            if time.time() - float(payload.get('ts', 0)) > max_age:
                return None
            return payload.get('data')
        except Exception:
            return None

    def set(self, key, data):
        try:
            with open(self._path(key), 'w', encoding='utf-8') as handle:
                json.dump({'ts': time.time(), 'data': data}, handle, ensure_ascii=False)
            return True
        except Exception:
            return False

    def invalidate(self, key):
        try:
            os.remove(self._path(key))
        except OSError:
            pass

    def clear(self):
        try:
            for name in os.listdir(self.directory):
                if name.endswith('.json'):
                    os.remove(os.path.join(self.directory, name))
        except OSError:
            pass
