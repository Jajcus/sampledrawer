
import logging

from PySide2.QtGui import QIcon

from cffi import FFI

from ..audiodrivers.driver import AudioState

ffi = FFI()
logger = logging.getLogger("player")


class Player:
    def __init__(self, app, window):
        self.app = app
        self.window = window
        self.driver = self.app.audio_driver

        self.play_icon = QIcon.fromTheme("media-playback-start")
        self.pause_icon = QIcon.fromTheme("media-playback-pause")

        self.window.play_btn.clicked.connect(self.play_pause_clicked)
        self.window.stop_btn.clicked.connect(self.stop_clicked)

        if self.driver:
            self.driver.set_player(self)
        else:
            self.window.stop_btn.setEnabled(False)
            self.window.play_btn.setEnabled(False)

    def audio_position_changed(self, pos):
        logger.debug("Audio position: %r", pos)
        self.window.waveform.set_cursor_position(pos)

    def audio_state_changed(self, state):
        if state == AudioState.PLAYING:
            self.window.stop_btn.setEnabled(False)
            self.window.play_btn.setIcon(self.pause_icon)
        else:
            self.window.stop_btn.setEnabled(False)
            self.window.play_btn.setIcon(self.play_icon)

    def rewind(self):
        if not self.driver:
            return
        self.driver.stop()
        if self.current_file:
            self.driver.set_source(self.current_file)
            self.window.play_btn.setEnabled(True)
        else:
            self.driver.set_source(None)
            self.window.play_btn.setEnabled(False)

    def file_selected(self, path):
        self.current_file = path
        if not self.driver:
            return
        self.driver.set_source(path)
        self.window.play_btn.setEnabled(True)

    def play_pause_clicked(self):
        logger.debug("Play/Pause clicked")
        if self.driver.audio_state == AudioState.PLAYING:
            logger.debug("pausing")
            self.window.play_btn.setIcon(self.play_icon)
            self.window.play_btn.setText("Play")
            self.driver.pause()
        elif self.driver.audio_state in (AudioState.PLAYING, AudioState.STOPPED):
            logger.debug("starting/resuming")
            self.driver.play()
            self.window.play_btn.setIcon(self.pause_icon)
            self.window.play_btn.setText("Pause")
            self.window.stop_btn.setEnabled(True)
        else:
            logger.debug("Ignoring Play/Pause in unexpected state")

    def stop_clicked(self):
        self.rewind()
