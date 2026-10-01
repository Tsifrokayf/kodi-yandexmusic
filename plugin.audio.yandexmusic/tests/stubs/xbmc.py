"""Minimal xbmc module stub for tests."""
LOGDEBUG = 0
LOGINFO = 1
LOGNOTICE = 2
LOGWARNING = 3
LOGERROR = 4
LOGSEVERE = 5
LOGFATAL = 6
LOGNONE = 7

BUILTINS = []
INFOLABELS = {}


def log(msg, level=LOGDEBUG):
    pass


def executebuiltin(cmd):
    BUILTINS.append(cmd)


def getLocalizedString(string_id):
    return str(string_id)


def getInfo(label):
    return ''


def getInfoLabel(label):
    return INFOLABELS.get(label, '')


class Player(object):
    playing = False
    playing_video = False

    def isPlayingAudio(self):
        return type(self).playing

    def isPlayingVideo(self):
        return type(self).playing_video

    def isPlaying(self):
        return type(self).playing or type(self).playing_video


class Monitor(object):
    def abortRequested(self):
        return False

    def waitForAbort(self, timeout=0):
        return False
