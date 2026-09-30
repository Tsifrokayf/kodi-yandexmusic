"""Minimal xbmcgui module stub for tests."""
INPUT_ALPHANUM = 0
INPUT_NUMERIC = 1


class ListItem(object):
    def __init__(self, label='', label2='', path='', offscreen=False):
        self.label = label
        self.label2 = label2
        self.path = path
        self.offscreen = offscreen
        self.art = {}
        self.info = {}
        self.properties = {}
        self.menu = []

    def setLabel(self, label):
        self.label = label

    def getLabel(self):
        return self.label

    def setInfo(self, type_, info):
        self.info[type_] = info

    def setArt(self, art):
        self.art.update(art)

    def getProperty(self, key):
        return self.properties.get(key, '')

    def setProperty(self, key, value):
        self.properties[key] = value

    def addContextMenuItems(self, items):
        self.menu.extend(items)

    def setPath(self, path):
        self.path = path

    def getPath(self):
        return self.path


class Dialog(object):
    def notification(self, heading, message, icon='', time=5000, sound=True):
        return None

    def ok(self, heading, message):
        return True

    def yesno(self, heading, message):
        return False

    def input(self, heading, default='', type_=0):
        return default

    def select(self, heading, options):
        return -1


class DialogProgress(object):
    def create(self, heading, message=''):
        self._canceled = False

    def iscanceled(self):
        return getattr(self, '_canceled', False)

    def update(self, percent, message=''):
        pass

    def close(self):
        pass
