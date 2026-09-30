"""Download tracks into the addon profile before playback.

Gives the user a Yandex-Music-style progress bar before the track starts and
makes replays instant. Falls back to streaming on any failure or cancel.
"""
import logging
import os
import time
import urllib.request

log = logging.getLogger(__name__)

CHUNK = 128 * 1024
MAX_AGE = 7 * 24 * 3600
MAX_FILES = 40
MAX_BYTES = 700 * 1024 * 1024
USER_AGENT = 'Mozilla/5.0 (Kodi yandexmusic plugin)'


def cache_dir(profile):
    path = os.path.join(profile, 'audio_cache')
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        pass
    return path


def _safe_name(track_id):
    text = ''.join(ch if ch.isalnum() or ch in '-_.' else '_' for ch in str(track_id))
    return (text or 'track') + '.audio'


def cached_path(profile, track_id):
    return os.path.join(cache_dir(profile), _safe_name(track_id))


def is_fresh(full):
    try:
        return os.path.getsize(full) > 0 and \
            time.time() - os.path.getmtime(full) <= MAX_AGE
    except OSError:
        return False


def _remove(full):
    try:
        os.remove(full)
    except OSError:
        pass


def _cleanup(path):
    entries = []
    for name in os.listdir(path):
        full = os.path.join(path, name)
        try:
            st = os.stat(full)
        except OSError:
            continue
        entries.append((st.st_mtime, full, st.st_size))
    now = time.time()
    fresh = []
    for mtime, full, size in entries:
        if now - mtime > MAX_AGE:
            _remove(full)
        else:
            fresh.append((mtime, full, size))
    fresh.sort(reverse=True)
    total = 0
    for index, (_mtime, full, size) in enumerate(fresh):
        total += size
        if index >= MAX_FILES or total > MAX_BYTES:
            _remove(full)


def fetch(url, dest, on_progress=None, should_cancel=None):
    """Download url to dest atomically; returns byte count."""
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    resp = urllib.request.urlopen(req, timeout=60)
    total = int(resp.headers.get('Content-Length') or 0)
    tmp = dest + '.part'
    done = 0
    last = -1
    try:
        with open(tmp, 'wb') as out:
            while True:
                if should_cancel is not None and should_cancel():
                    raise KeyboardInterrupt()
                chunk = resp.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if on_progress is not None and total:
                    percent = int(done * 100 / total)
                    if percent != last:
                        last = percent
                        on_progress(percent)
        if total and done < total:
            raise IOError('truncated download: {0}/{1}'.format(done, total))
    except BaseException:
        _remove(tmp)
        raise
    finally:
        try:
            resp.close()
        except Exception:
            pass
    os.replace(tmp, dest)
    return done


def preload_track(profile, url, track_id, on_progress=None, should_cancel=None):
    """Return a local file path when ready, else None (stream instead)."""
    dest = cached_path(profile, track_id)
    if is_fresh(dest):
        return dest
    _cleanup(cache_dir(profile))
    try:
        fetch(url, dest, on_progress, should_cancel)
        return dest
    except KeyboardInterrupt:
        _remove(dest)
        return None
    except Exception as error:
        log.info('preload failed for %s: %s', track_id, error)
        _remove(dest)
        return None
