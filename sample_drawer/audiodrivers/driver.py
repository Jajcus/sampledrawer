"""Audio driver base class."""

import enum

import logging

logger = logging.getLogger("audiodrivers.driver")


@enum.unique
class AudioState(enum.Enum):
    INVALID = -1
    UNINITIALIZED = 0
    STOPPED = 1
    PAUSED = 2
    PLAYING = 3


class AudioDriverError(Exception):
    pass


class AudioDriver:
    driver_name = None
    registered_drivers = {}

    def __init__(self, args=None):
        self.audio_state = AudioState.UNINITIALIZED
        self.position = 0.0
        self.duration = 0.0
        self.source = None
        self.player = None

    def __repr__(self):
        return "<{} ({})>".format(self.__class__.__name__, self.driver_name)

    @classmethod
    def register_driver(cls):
        name = cls.driver_name
        AudioDriver.registered_drivers[name] = cls

    def set_player(self, player):
        """Set object that will receive position/status changes."""
        self.player = player

    def set_source(self, filename):
        """Set path to the file to play."""
        self.source = filename

    def get_position(self):
        """Get current stream position (in seconds)."""
        return self.position

    def _set_position(self, position):
        """Called to update current position."""
        if position == self.position:
            return
        self.position = position
        if self.player:
            self.player.audio_position_changed(position)

    def _set_audio_state(self, state):
        """Called to update current audio state."""
        if self.audio_state == state:
            return
        self.audio_state = state
        if self.player:
            self.player.audio_state_changed(state)

    def play(self):
        """Start playback from the current source."""
        raise NotImplementedError

    def pause(self):
        """Pause current playback."""
        raise NotImplementedError

    def stop(self):
        """Stop current playback (rewind source to the beginning)."""
        raise NotImplementedError


class PositionPollingAudioDriver(AudioDriver):
    """Base class for audio drivers that need poling for position (do not
    update it automatically).

    Uses QTimer to make sure self.player.audio_position_changed() is called from the right thread
    (Qt main loop)."""
    def __init__(self, args=None):
        AudioDriver.__init__(self, args)
        from PySide2.QtCore import QTimer
        self._timer = QTimer()
        self._timer.timeout.connect(self._poll_position)
        self._timer.start(100)

    def _poll_position(self):
        position = self.get_position()
        self._set_position(position)

    def get_position(self):
        """Determine current stream position (in seconds).

        Return 0.0 if unknown."""
        raise NotImplementedError
