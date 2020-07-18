
import math
import os
import logging

from functools import cached_property, partial

from soundfile import SoundFile
import numpy

from PySide2.QtCore import QObject, Slot, Signal, QRunnable, QThreadPool

from .lrucache import LRUCache
from .samplemetadata import SampleMetadata

WAVEFORM_RESOLUTION = 200 # samples per second

logger = logging.getLogger("sampleanalyzer")

class FileKey:
    """For reliably using filenames as keys in a cache."""
    def __init__(self, path):
        if isinstance(path, FileKey):
            self.path = path.path
            self.stat = path.stat
        else:
            self.path = str(path)
    def __repr__(self):
        return "FileKey({!r})".format(self.path)
    def __str__(self):
        return self.path
    @cached_property
    def stat(self):
        try:
            stat = os.stat(self.path)
            logger.debug("FileKey: %r: %r", self.path, stat)
            return stat
        except OSError as err:
            logger.debug("FileKey: %r: %s", self.path, err)
            return None
    def __hash__(self):
        if self.stat:
            return hash((self.path, self.stat.st_size, self.stat.st_mtime))
        else:
            return hash(self.path)
    def __eq__(self, other):
        return (self.path == other.path
                and self.stat
                and self.stat.st_size == other.stat.st_size
                and self.stat.st_mtime == other.stat.st_mtime)


class SampleAnalyzerWorker(QRunnable):

    def __init__(self, filename):
        QRunnable.__init__(self)
        self.filename = filename
        self.signals = self.Signals()

    @Slot()
    def run(self):
        """
        Gather sample meta-data in the background.
        """

        try:
            file_info = self.load_data()
            self.signals.finished.emit(file_info)
        except (IOError, RuntimeError) as err:
            logger.error("Cannot load %r: %s", str(self.filename), err)
            self.signals.error.emit(err)
        logger.debug("Thread complete")

    def load_data(self):
        logger.debug("Thread start")
        file_info = { "filename": str(self.filename) }
        with SoundFile(str(self.filename)) as snd_file:
            logger.debug("name: %r", snd_file.name)
            logger.debug("mode: %r", snd_file.mode)
            logger.debug("samplerate: %r", snd_file.samplerate)
            file_info["samplerate"] = snd_file.samplerate
            logger.debug("frames: %r", snd_file.frames)
            file_info["duration"] = float(snd_file.frames) / snd_file.samplerate
            logger.debug("channels: %r", snd_file.channels)
            logger.debug("format: %r", snd_file.format)
            file_info["format"] = snd_file.format
            logger.debug("subtype: %r", snd_file.subtype)
            file_info["subtype"] = snd_file.subtype
            logger.debug("endian: %r", snd_file.endian)
            logger.debug("format_info: %r", snd_file.format_info)
            logger.debug("subtype_info: %r", snd_file.subtype_info)
            logger.debug("sections: %r", snd_file.sections)
            logger.debug("closed: %r", snd_file.closed)
            logger.debug("extra_info: %r", snd_file.extra_info)
            frames = snd_file.read()
            peek_level = max(numpy.amax(frames), -numpy.amin(frames))
            if not peek_level:
                peek_level_db = -math.inf
                file_info["peek_level"] = peek_level_db
            else:
                try:
                    peek_level_db = 20*math.log10(peek_level)
                    file_info["peek_level"] = peek_level_db
                except ValueError:
                    logger.error("Cannot convert %r to dBFS", peek_level)
            logger.debug("%r frames read", len(frames))
        return file_info
    class Signals(QObject):
        finished = Signal(dict)
        error = Signal(str)

class SampleAnalyzer(QObject):
    def __init__(self):
        QObject.__init__(self)
        self.threadpool = QThreadPool()
        self._waiting_for_metadata = {}
        self._cache = LRUCache(maxsize=10)

    def request_file_metadata(self, path, callback = None):
        if isinstance(path, FileKey):
            file_key = path
        else:
            file_key = FileKey(path)
        file_info = self._cache.get(file_key)
        if file_info is not None:
            metadata = SampleMetadata.from_file_info(file_info)
            callback(file_key, metadata)
            return
        logger.debug("Metadata for %r not known yet", str(path))
        waiting_list = self._waiting_for_metadata.get(file_key)
        if waiting_list:
            logger.debug("Already requested, adding to the waiting list")
            waitin_list.append(callback)
        else:
            worker = SampleAnalyzerWorker(file_key)
            self.threadpool.start(worker)
            our_callback = partial(self._file_info_received, file_key)
            self._waiting_for_metadata[file_key] = [callback]
            worker.signals.finished.connect(Slot()(our_callback))

    def _file_info_received(self, file_key, file_info):
        logger.debug("file_info_received for %r called with %r", file_key, file_info)
        self._cache.put(file_key, file_info)
        callbacks = self._waiting_for_metadata.pop(file_key)
        metadata = SampleMetadata.from_file_info(file_info)
        for callback in callbacks:
            callback(file_key, metadata)

    def get_file_metadata(self, path):
        if not isinstance(path, FileKey):
            path = FileKey(path)
        file_info = self._cache.get(path)
        if file_info is not None:
            return SampleMetadata.from_file_info(file_info)
        else:
            return None

