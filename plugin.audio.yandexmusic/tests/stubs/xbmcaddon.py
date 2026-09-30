"""Minimal xbmcaddon module stub for tests."""
import os
import tempfile


class Addon(object):
    def __init__(self, id=None):
        self._id = id or 'plugin.audio.yandexmusic'
        self._settings = {}

    def getAddonInfo(self, key):
        infos = {
            'id': self._id,
            'name': 'Yandex Music (test)',
            'version': '0.0.0',
            'author': 'test',
            'path': os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))),
            'profile': os.path.join(tempfile.gettempdir(), 'ymkodi-test-profile'),
            'icon': '',
        }
        return infos.get(key, '')

    def getLocalizedString(self, string_id):
        return str(string_id)

    def getSetting(self, key):
        return self._settings.get(key, '')

    def setSetting(self, key, value):
        self._settings[key] = value

    def openSettings(self):
        pass
