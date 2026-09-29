"""OAuth session storage (pure, testable)."""
import json
import os
import time


class SessionStore(object):
    def __init__(self, path):
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            try:
                os.makedirs(parent, exist_ok=True)
            except OSError:
                pass

    def load(self):
        try:
            with open(self.path, 'r', encoding='utf-8') as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def save(self, access_token, refresh_token=None, expires_in=None):
        data = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'obtained_at': time.time(),
            'expires_in': expires_in,
        }
        with open(self.path, 'w', encoding='utf-8') as handle:
            json.dump(data, handle)
        return data

    def has_token(self):
        return bool(self.load().get('access_token'))

    def expired(self, margin=120):
        data = self.load()
        if not data.get('access_token'):
            return True
        expires_in = data.get('expires_in')
        if not expires_in:
            return False
        obtained_at = data.get('obtained_at') or 0
        return time.time() >= obtained_at + float(expires_in) - margin

    def clear(self):
        try:
            os.remove(self.path)
        except OSError:
            pass
