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
COND_VISIBILITY = {}


def log(msg, level=LOGDEBUG):
    pass


def executebuiltin(cmd):
    BUILTINS.append(cmd)


def getCondVisibility(condition):
    return bool(COND_VISIBILITY.get(condition, False))


def getLocalizedString(string_id):
    return str(string_id)


def getInfo(label):
    return ''


def getInfoLabel(label):
    return INFOLABELS.get(label, '')


class Player(object):
    playing = False
    playing_video = False
    playing_file = ''
    total_time = 0.0
    current_time = 0.0

    def isPlayingAudio(self):
        return type(self).playing

    def isPlayingVideo(self):
        return type(self).playing_video

    def isPlaying(self):
        return type(self).playing or type(self).playing_video

    def getPlayingFile(self):
        return type(self).playing_file

    def getTotalTime(self):
        return type(self).total_time

    def getTime(self):
        return type(self).current_time


class Monitor(object):
    def abortRequested(self):
        return False

    def waitForAbort(self, timeout=0):
        return False
