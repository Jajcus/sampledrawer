"""Audio decoding and playback through Qt APIs."""

import logging

from PySide2.QtCore import QByteArray
from PySide2.QtMultimedia import QAudioDeviceInfo, QAudioDecoder, QAudioOutput, QAudio

from cffi import FFI

from .driver import AudioState, AudioDriver, AudioDriverError

ffi = FFI()
logger = logging.getLogger("audiodrivers.qt")


class QtAudioDriver(AudioDriver):
    driver_name = "qt"

    def __init__(self, args=None):
        AudioDriver.__init__(self, args)
        if args and args.audio_device:
            available_devices = {}
            for device in QAudioDeviceInfo.availableDevices(QAudio.AudioOutput):
                available_devices[device.deviceName()] = device
            try:
                device = available_devices[args.audio_device]
            except KeyError:
                logger.error("Unknown audio device: %r", self.app.args.audio_device)
                logger.info("Available devices:")
                for device_name in available_devices:
                    logger.info("    %r", device_name)
                raise AudioDriverError("Unsupported audio device")
        else:
            device = QAudioDeviceInfo.defaultOutputDevice()

        playback_format = device.preferredFormat()
        self.decoder = QAudioDecoder()
        self.decoder.setAudioFormat(playback_format)
        self.output = QAudioOutput(device, playback_format)

        self.device_name = device.deviceName()
        self.duration = None
        self.bytes_written = 0
        self.last_frame = b""
        self.starting = False
        self.output_dev = None
        self.current_file = None
        self.current_buffer = None
        self.current_buffer_pos = 0

        self.output.stateChanged.connect(self.output_state_changed)
        self.output.notify.connect(self.tick)

        self.decoder.error.connect(self.decoder_error)
        self.decoder.finished.connect(self.decoder_finished)
        self.decoder.stateChanged.connect(self.decoder_state_changed)
        self.decoder.positionChanged.connect(self.decoder_pos_changed)
        self.decoder.bufferReady.connect(self.buffer_ready)

    def __repr__(self):
        return "<{} ({}) device={!r}>".format(self.__class__.__name__,
                                              self.driver_name,
                                              self.device_name)

    def set_source(self, filename):
        super().set_source(filename)
        self._rewind()

    def decoder_error(self, err):
        logger.error("Decoder error: %r", err)

    def decoder_finished(self):
        logger.debug("Decoder finished")
        if self.output_dev:
            self.playing = False
            buf_size = self.output.bufferSize()
            reminder = self.bytes_written % buf_size
            if reminder and self.last_frame:
                logger.debug("only %r bytes written to last %r bytes buffer",
                             reminder, buf_size)
                # make sure multiple of the buffer size has been written
                frames_missing = (buf_size - reminder) // len(self.last_frame)
                padding = self.last_frame * frames_missing
                logger.debug("Padding with %r frames (%r bytes)",
                             frames_missing, len(padding))
                self.output_dev.write(padding)
            self.output_dev.close()
            self.output_dev = None

    def decoder_pos_changed(self, pos):
        logger.debug("Decoder position: %i", pos)
        time_pos = pos / 1000.0
        self.set_position(time_pos)

    def decoder_state_changed(self, state):
        logger.debug("Decoder state: %r", state)

    def buffer_ready(self):
        logger.debug("Buffer ready")
        self.push_data()

    def output_state_changed(self, state):
        logger.debug("Output state changed to: %r", state)
        if state == QAudio.State.IdleState and not self.starting:
            logger.debug("playback finished")
            self._rewind()
        # do not call push_data() here, as this is called from push_data()

    def tick(self):
        logger.debug("tick")
        self.push_data()

    def push_data(self):
        logger.debug("push_data() start")
        if not self.output_dev:
            logger.debug("no output device")
            return
        frame_size = self.output.format().bytesPerFrame()
        while True:
            logger.debug("push_data...")
            buf = self.current_buffer
            if buf is not None:
                length = buf.byteCount()
            else:
                length = 0
            if buf is None or self.current_buffer_pos >= length:
                if not self.decoder.bufferAvailable():
                    logger.debug("No buffer available")
                    break
                buf = self.decoder.read()
                logger.debug("New buffer acquired: %r", buf)
                length = buf.byteCount()
                self.current_buffer = buf
                self.current_buffer_pos = 0
            data = buf.constData()
            logger.debug("data: 0x%016X, length: %i", int(data), length)
            data_ptr = ffi.cast("void *", int(data))
            data_bytes = ffi.buffer(data_ptr, length)[self.current_buffer_pos:]
            to_write = len(data_bytes)
            data_arr = QByteArray.fromRawData(data_bytes)
            bytes_written = self.output_dev.write(data_arr)
            if bytes_written > frame_size:
                self.last_frame = data_arr[bytes_written - frame_size:bytes_written].data()
                logger.debug("Last frame: %r", self.last_frame)
            self.current_buffer_pos += bytes_written
            self.bytes_written = bytes_written
            logger.debug("%i of %i bytes written, pos: %i",
                         bytes_written, to_write, self.current_buffer_pos)
            if self.current_buffer_pos >= length:
                self.current_buffer = None
            if bytes_written < to_write:
                break

    def _rewind(self):
        self.output.stop()
        self.output.reset()
        self.bytes_written = 0
        self.current_buffer = None
        self.output_dev = None
        if self.source:
            self.decoder.setSourceFilename(self.source)
            self._set_audio_state(AudioState.STOPPED)
            if self.player:
                self.player.audio_position_changed(0)
        else:
            self.decoder.stop()
            self.audio_state = AudioState.UNINITIALIZED

    def play(self):
        if self.audio_state == AudioState.PLAYING:
            pass
        elif self.audio_state == AudioState.PAUSED:
            logger.debug("resuming")
            self.starting = True
            try:
                self.output.resume()
            finally:
                self.starting = False
            self._set_audio_state(AudioState.PLAYING)
            self.push_data()
        else:
            logger.debug("starting")
            self._rewind()
            self.starting = True
            try:
                self.bytes_written = 0
                self.decoder.start()
                self.output_dev = self.output.start()
                fmt = self.output.format()
                tick_interval = fmt.durationForBytes(self.output.periodSize()) / 1000
                logger.debug("tick interval: %i", tick_interval)
                self.output.setNotifyInterval(tick_interval)
                self.push_data()
            finally:
                self.starting = False
            self._set_audio_state(AudioState.PLAYING)

    def stop(self):
        logger.debug("stopping")
        self._rewind()

    def pause(self):
        if self.output.state() == QAudio.State.ActiveState:
            logger.debug("pausing")
            self.output.suspend()
            self._set_audio_state(AudioState.PAUSED)


QtAudioDriver.register_driver()
