"""Karaoke overlay: auto-scrolling lyrics on top of the playing track."""
import logging

import xbmcgui

from .lyrics import line_index

log = logging.getLogger(__name__)

CLOSE_ACTIONS = {10, 13, 92}  # previous menu, stop, nav back


class KaraokeOverlay(xbmcgui.Window):
    def __init__(self, title, entries, hint=''):
        xbmcgui.Window.__init__(self)
        self._entries = list(entries)
        self._alive = True
        width = self.getWidth() or 1280
        height = self.getHeight() or 720
        self._title = xbmcgui.ControlLabel(
            0, int(height * 0.16), width, 40, title or '',
            font='font16', alignment=2, textColor='FF9BE0FF')
        self._current = xbmcgui.ControlLabel(
            40, int(height * 0.40), width - 80, 90, '',
            font='font30', alignment=2, textColor='FFFFE9A3')
        self._next = xbmcgui.ControlLabel(
            60, int(height * 0.57), width - 120, 50, '',
            font='font14', alignment=2, textColor='FF909090')
        self._hint = xbmcgui.ControlLabel(
            0, height - 50, width, 30, hint or '',
            font='font12', alignment=2, textColor='FF666666')
        for control in (self._title, self._current, self._next, self._hint):
            self.addControl(control)
        self._shown = None

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
        self._current.setLabel(current)
        self._next.setLabel(following)
        self._shown = index

    def run(self, monitor, player):
        """Drive the overlay until stopped, track end, Kodi shutdown or close."""
        self.render(-1)
        last = None
        while self._alive and not monitor.abortRequested():
            monitor.waitForAbort(0.25)
            if monitor.abortRequested() or not self._alive:
                break
            if not player.isPlaying():
                break
            try:
                moment = player.getTime()
            except RuntimeError:
                break
            index = line_index(self._entries, moment)
            if index != last:
                self.render(index)
                last = index
        try:
            self.close()
        except RuntimeError:
            log.debug('karaoke window already closed', exc_info=True)
