"""Lyrics helpers: LRC parsing and plain-text cleanup (no xbmc deps)."""
import re

_LRC_TAG = re.compile(r'\[(\d{1,3}):(\d{1,2})(?:[.:](\d{1,6}))?\]')
_LEADING_TAGS = re.compile(r'(?:\[\d{1,3}:\d{1,2}(?:[.:]\d{1,6})?\])+')


def parse_lrc(text):
    """Parse LRC text into a sorted list of (seconds, line) tuples."""
    entries = []
    for raw in (text or '').splitlines():
        line = raw.strip()
        if not line:
            continue
        tags = _LRC_TAG.findall(line)
        if not tags:
            continue
        content = _LEADING_TAGS.sub('', line).strip()
        if not content:
            continue
        for minutes, seconds, frac in tags:
            moment = int(minutes) * 60 + int(seconds)
            if frac:
                moment += int(frac.ljust(3, '0')[:3]) / 1000.0
            entries.append((moment, content))
    entries.sort(key=lambda item: item[0])
    return entries


def plain_from_lrc(text):
    """Strip LRC time tags, keep the lyric lines."""
    lines = []
    for raw in (text or '').splitlines():
        line = _LEADING_TAGS.sub('', raw).strip()
        if line:
            lines.append(line)
    return '\n'.join(lines)


def line_index(entries, moment):
    """Index of the lyric line active at `moment` seconds (-1 before first)."""
    index = -1
    for i, (time, _content) in enumerate(entries):
        if time <= moment + 0.001:
            index = i
        else:
            break
    return index
