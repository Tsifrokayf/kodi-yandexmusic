"""Karaoke overlay: auto-scrolling lyrics on top of the playing track."""
import logging
import uuid

import xbmc
import xbmcgui

from .lyrics import line_index

log = logging.getLogger(__name__)

CLOSE_ACTIONS = {10, 13, 92}  # previous menu, stop, nav back
TOKEN_PROPERTY = 'plugin.audio.yandexmusic.karaoke'
# Auto lyrics live only in the full-screen player (visualisation window).
# NB: getCondVisibility rejects '||' here (Misplaced |), check both windows.
FULLSCREEN_CONDITIONS = ('Window.IsActive(visualisation)',
                         'Window.IsActive(fullscreenvideo)')


def in_fullscreen():
    return any(bool(xbmc.getCondVisibility(cond))
               for cond in FULLSCREEN_CONDITIONS)


def release_overlay(window_id=10000):
    """Drop our overlay token so any live overlay closes (frees modal input)."""
    try:
        xbmcgui.Window(window_id).clearProperty(TOKEN_PROPERTY)
    except Exception:
        log.debug('karaoke token clear failed', exc_info=True)


def wait_overlay_closed(monitor, ticks=8, step=0.25):
    """Wait until no modal dialog blocks window activation (overlay closing)."""
    for _ in range(ticks):
        if not xbmc.getCondVisibility('System.HasActiveModalDialog'):
            return True
        if monitor.abortRequested():
            return False
        monitor.waitForAbort(step)
    return not xbmc.getCondVisibility('System.HasActiveModalDialog')


class KaraokeOverlay(xbmcgui.WindowDialog):
    def __new__(cls, *args, **kwargs):
        # SWIG __new__ rejects constructor arguments.
        return super().__new__(cls)

    def __init__(self, title, entries, hint=''):
        xbmcgui.WindowDialog.__init__(self)
        self._entries = list(entries)
        self._alive = True
        width = self.getWidth() or 1280
        height = self.getHeight() or 720
        # ControlLabel has no shadowColor here: draw a black copy underneath.
        self._title = self._pair(
            0, int(height * 0.14), width, 50, title or '',
            'font32', 'FF9BE0FF')
        self._current = self._pair(
            40, int(height * 0.38), width - 80, 110, '',
            'font45', 'FFFFE9A3')
        self._next = self._pair(
            60, int(height * 0.57), width - 120, 60, '',
            'font27', 'FFB0B0B0')
        self._hint = self._pair(
            0, height - 54, width, 34, hint or '',
            'font13', 'FF909090')
        self._shown = None

    def _pair(self, x, y, w, h, text, font, color, shift=2):
        shadow = xbmcgui.ControlLabel(
            x + shift, y + shift, w, h, text, font=font, alignment=2,
            textColor='FF000000')
        label = xbmcgui.ControlLabel(
            x, y, w, h, text, font=font, alignment=2, textColor=color)
        self.addControl(shadow)
        self.addControl(label)
        return label, shadow

    def _set_pair(self, pair, text):
        label, shadow = pair
        label.setLabel(text)
        shadow.setLabel(text)

    def onAction(self, action):
        try:
            if action.getId() in CLOSE_ACTIONS:
                self._alive = False
        except Exception:
            log.debug('karaoke onAction failed', exc_info=True)

    def is_alive(self):
        return self._alive

    def render(self, index):
        lines = [content for _moment, content in self._entries]
        if index < 0:
            current = lines[0] if lines else ''
            following = lines[1] if len(lines) > 1 else ''
        else:
            current = lines[index] if index < len(lines) else ''
            following = lines[index + 1] if index + 1 < len(lines) else ''
        self._set_pair(self._current, current)
        self._set_pair(self._next, following)
        self._shown = index

    def run(self, monitor, player, require_fullscreen=False):
        """Drive the overlay until stopped, track end, Kodi shutdown or close.

        require_fullscreen: exit as soon as the full-screen player window is
        no longer active (auto karaoke must not linger over other windows).
        """
        self.render(-1)
        # Single-instance guard: when the next track starts a fresh overlay,
        # the previous one exits instead of stacking on top of it.
        token = uuid.uuid4().hex
        window = xbmcgui.Window(10000)
        try:
            window.setProperty(TOKEN_PROPERTY, token)
        except Exception:
            log.debug('karaoke token set failed', exc_info=True)
            token = None
        try:
            playing_file = player.getPlayingFile()
        except RuntimeError:
            playing_file = ''
        try:
            self.show()
        except RuntimeError:
            log.debug('karaoke show failed', exc_info=True)
            if token is not None:
                try:
                    if window.getProperty(TOKEN_PROPERTY) == token:
                        window.clearProperty(TOKEN_PROPERTY)
                except Exception:
                    pass
            return
        last = None
        while self._alive and not monitor.abortRequested():
            monitor.waitForAbort(0.25)
            if monitor.abortRequested() or not self._alive:
                break
            if not player.isPlaying():
                break
            if token is not None and window.getProperty(TOKEN_PROPERTY) != token:
                break  # a newer overlay took over
            if require_fullscreen and not in_fullscreen():
                break  # the full-screen player was closed
            if playing_file:
                try:
                    if player.getPlayingFile() != playing_file:
                        break  # the track changed
                except RuntimeError:
                    break
            try:
                moment = player.getTime()
            except RuntimeError:
                break
            index = line_index(self._entries, moment)
            if index != last:
                self.render(index)
                last = index
        if token is not None:
            try:
                if window.getProperty(TOKEN_PROPERTY) == token:
                    window.clearProperty(TOKEN_PROPERTY)
            except Exception:
                log.debug('karaoke token clear failed', exc_info=True)
        try:
            self.close()
        except RuntimeError:
            log.debug('karaoke window already closed', exc_info=True)
