
import logging

from PySide2.QtCore import Slot, QByteArray
from PySide2.QtGui import QIcon
from PySide2.QtMultimedia import QAudioDeviceInfo, QAudioDecoder, QAudioOutput, QAudio

from cffi import FFI

ffi = FFI()
logger = logging.getLogger("player")


class Player:
    def __init__(self, app, window):
        self.app = app
        self.window = window

        self.play_icon = QIcon.fromTheme("media-playback-start")
        self.pause_icon = QIcon.fromTheme("media-playback-pause")

        if self.app.args.audio_device:
            available_devices = {}
            for device in QAudioDeviceInfo.availableDevices(QAudio.AudioOutput):
                available_devices[device.deviceName()] = device
            try:
                device = available_devices[self.app.args.audio_device]
            except KeyError:
                logger.error("Unknown audio device: %r", self.app.args.audio_device)
                logger.info("Available devices:")
                for device_name in available_devices:
                    logger.info("    %r", device_name)
                self.app.exit(1)
                device = QAudioDeviceInfo.defaultOutputDevice()
        else:
            device = QAudioDeviceInfo.defaultOutputDevice()
        playback_format = device.preferredFormat()
        self.decoder = QAudioDecoder()
        self.decoder.setAudioFormat(playback_format)
        self.output = QAudioOutput(device, playback_format)

        self.duration = None
        self.bytes_written = 0
        self.last_frame = b""
        self.starting = False
        self.output_dev = None
        self.current_file = None
        self.current_buffer = None
        self.current_buffer_pos = 0

        self.window.play_btn.clicked.connect(self.play_pause_clicked)
        self.window.stop_btn.clicked.connect(self.stop_clicked)

        self.output.stateChanged.connect(self.output_state_changed)
        self.output.notify.connect(self.tick)

        self.decoder.error.connect(self.decoder_error)
        self.decoder.finished.connect(self.decoder_finished)
        self.decoder.stateChanged.connect(self.decoder_state_changed)
        self.decoder.positionChanged.connect(self.decoder_pos_changed)
        self.decoder.bufferReady.connect(self.buffer_ready)

    @Slot(QAudioDecoder.Error)
    def decoder_error(self, err):
        logger.error("Decoder error: %r", err)

    @Slot()
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

    @Slot(int)
    def decoder_pos_changed(self, pos):
        logger.debug("Decoder position: %i", pos)
        time_pos = pos / 1000.0
        self.window.waveform.set_cursor_position(time_pos)

    @Slot(QAudioDecoder.State)
    def decoder_state_changed(self, state):
        logger.debug("Decoder state: %r", state)

    @Slot()
    def buffer_ready(self):
        logger.debug("Buffer ready")
        self.push_data()

    @Slot(QAudio.State)
    def output_state_changed(self, state):
        logger.debug("Output state changed to: %r", state)
        if state == QAudio.State.IdleState and not self.starting:
            logger.debug("playback finished")
            self.rewind()
        # do not call push_data() here, as this is called from push_data()

    @Slot()
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

    def rewind(self):
        self.output.stop()
        self.output.reset()
        self.bytes_written = 0
        self.current_buffer = None
        self.output_dev = None
        self.window.waveform.set_cursor_position(0)
        self.window.stop_btn.setEnabled(True)
        self.window.play_btn.setIcon(self.play_icon)
        self.window.play_btn.setText("Play")
        if self.current_file:
            self.decoder.setSourceFilename(self.current_file)
            self.window.play_btn.setEnabled(True)
        else:
            self.decoder.stop()
            self.window.play_btn.setEnabled(False)

    @Slot(str)
    def file_selected(self, path):
        self.current_file = path
        self.rewind()

    @Slot()
    def play_pause_clicked(self):
        logger.debug("Play/Pause clicked")
        if self.output.state() == QAudio.State.ActiveState:
            logger.debug("pausing")
            self.window.play_btn.setIcon(self.play_icon)
            self.window.play_btn.setText("Play")
            self.output.suspend()
        elif self.output.state() == QAudio.State.SuspendedState:
            logger.debug("resuming")
            self.starting = True
            try:
                self.output.resume()
            finally:
                self.starting = False
            self.window.play_btn.setIcon(self.pause_icon)
            self.window.play_btn.setText("Pause")
            self.push_data()
        elif not self.output_dev:
            logger.debug("starting")
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
                self.window.play_btn.setIcon(self.pause_icon)
                self.window.play_btn.setText("Pause")
                self.window.stop_btn.setEnabled(True)
            finally:
                self.starting = False
        else:
            logger.debug("Ignoring Play/Pause in unexpected state")

    @Slot()
    def stop_clicked(self):
        self.rewind()
