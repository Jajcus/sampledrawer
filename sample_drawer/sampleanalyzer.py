
import os
import logging

from functools import cached_property, lru_cache

from soundfile import SoundFile

from PySide2.QtCore import QObject, Slot, Signal, QRunnable, QThreadPool

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

    @Slot()
    def run(self):
        """
        Gather sample meta-data in the background.
        """
        logger.debug("Thread start")
        with SoundFile(str(self.filename)) as snd_file:
            logger.debug("name: %r", snd_file.name)
            logger.debug("mode: %r", snd_file.mode)
            logger.debug("samplerate: %r", snd_file.samplerate)
            logger.debug("frames: %r", snd_file.frames)
            logger.debug("channels: %r", snd_file.channels)
            logger.debug("format: %r", snd_file.format)
            logger.debug("subtype: %r", snd_file.subtype)
            logger.debug("endian: %r", snd_file.endian)
            logger.debug("format_info: %r", snd_file.format_info)
            logger.debug("subtype_info: %r", snd_file.subtype_info)
            logger.debug("sections: %r", snd_file.sections)
            logger.debug("closed: %r", snd_file.closed)
            logger.debug("extra_info: %r", snd_file.extra_info)
            while True:
                frames_read = snd_file.read(1000)
                logger.debug("%r frames read", len(frames_read))
                if len(frames_read) == 0:
                    break
        logger.debug("Thread complete")

class SampleAnalyzer(QObject):
    def __init__(self):
        QObject.__init__(self)
        self.threadpool = QThreadPool()

    @Slot(str)
    def request_file_metadata(self, path, callback = None):
        file_key = FileKey(path)
        try:
            return self._get_metadata(file_key)
        except KeyError:
            logger.debug("Metadata for %r not known yet")
        worker = SampleAnalyzerWorker(file_key)
        self.threadpool.start(worker)

    @lru_cache(maxsize = 100)
    def _get_metadata(self, file_key):
        raise KeyError(file_key)
