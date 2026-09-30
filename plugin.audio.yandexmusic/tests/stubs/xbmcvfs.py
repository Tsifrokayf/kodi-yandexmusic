"""Minimal xbmcvfs module stub for tests."""


def translatePath(path):
    return path


def exists(path):
    return False


def mkdir(path):
    return True


def mkdirs(path):
    return True


def delete(path):
    return True


def listdir(path):
    return ([], [])
