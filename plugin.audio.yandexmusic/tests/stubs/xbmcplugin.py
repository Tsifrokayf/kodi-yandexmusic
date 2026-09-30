"""Minimal xbmcplugin module stub for tests."""
SORT_METHOD_UNSORTED = 0

_added = []
_resolved = []


def addDirectoryItem(handle, url, listitem, isFolder=False, totalItems=0):
    _added.append((url, listitem, isFolder))
    return True


def endOfDirectory(handle, succeeded=True, updateListing=False, cacheToDisc=True):
    pass


def setContent(handle, content):
    pass


def addSortMethod(handle, sortMethod, label2Mask=''):
    pass


def setResolvedUrl(handle, succeeded, listitem):
    _resolved.append((succeeded, listitem))
