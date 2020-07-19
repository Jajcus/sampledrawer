
import logging

from PySide2.QtCore import Slot, QByteArray, QDataStream, QTimer
from PySide2.QtMultimedia import QAudioDeviceInfo, QAudioDecoder, QAudioFormat, QAudioOutput, QAudio

from cffi import FFI

ffi = FFI()
logger = logging.getLogger("sampleplayer")

class SamplePlayer:
    def __init__(self, controls):
        self.controls = controls
        self.controls.play_btn.clicked.connect(self.play_clicked)
        self.duration = None
        device = QAudioDeviceInfo.defaultOutputDevice()
        playback_format = device.preferredFormat()
        self.decoder = QAudioDecoder()
        self.decoder.setAudioFormat(playback_format)
        self.output = QAudioOutput(device, playback_format)
        self.output_dev = None
        self.current_buffer = None
        self.current_buffer_pos = 0

        self.output.stateChanged.connect(self.output_state_changed)
        self.decoder.error.connect(self.decoder_error)
        self.decoder.finished.connect(self.decoder_finished)
        self.decoder.stateChanged.connect(self.decoder_state_changed)
        self.decoder.positionChanged.connect(self.decoder_pos_changed)
        self.decoder.bufferReady.connect(self.buffer_ready)
        self.decoder.durationChanged.connect(self.duration_changed)
        self.decoder.formatChanged.connect(self.format_changed)
        self.decoder.metaDataChanged.connect(self.metadata_changed)

    @Slot(QAudioDecoder.Error)
    def decoder_error(self, err):
        logger.error("Decoder error: %r", err)

    @Slot()
    def decoder_finished(self):
        logger.info("Decoder finished")

    @Slot(int)
    def decoder_pos_changed(self, pos):
        logger.debug("Decoder position: %i", pos)

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
        self.push_data()

    @Slot()
    def tick(self):
        logger.debug("tick")
        self.push_data()

    def push_data(self):
        logger.debug("push_data() start")
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
            self.current_buffer_pos += bytes_written
            logger.debug("%i of %i bytes written, pos: %i",
                         bytes_written, to_write, self.current_buffer_pos)
            if self.current_buffer_pos >= length:
                self.current_buffer = None
            if bytes_written < to_write:
                break

    @Slot(int)
    def duration_changed(self, duration):
        logger.info("Duration: %i", duration)

    @Slot(QAudioFormat)
    def format_changed(self, fmt):
        logger.info("Format: %i", fmt)

    @Slot(str,  object)
    def metadata_changed(self, key, value):
        logger.info("metadata: %s: %r", key, value)

    @Slot(str)
    def file_selected(self, path):
        if path:
            self.decoder.setSourceFilename(path)
            self.controls.play_btn.setEnabled(True)

    @Slot()
    def play_clicked(self):
        self.decoder.start()
        self.output_dev = self.output.start()
        fmt = self.output.format()
        tick_interval = fmt.durationForBytes(self.output.periodSize()) / 1000
        logger.debug("tick interval: %i", tick_interval)
        self.output.setNotifyInterval(tick_interval)
        self.output.notify.connect(self.tick)
        self.push_data()


