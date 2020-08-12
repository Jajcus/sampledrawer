
import os
import logging

from functools import partial

from PySide2.QtCore import QObject, Signal, QRunnable, QThreadPool

from ..lru_cache import LRUCache
from ..file_analyzer import FileAnalyzer, FileKey
from ..metadata import Metadata

logger = logging.getLogger("gui.file_analyzer")

class FileAnalyzerWorker(QRunnable, FileAnalyzer):

    def __init__(self, path):
        QRunnable.__init__(self)
        FileAnalyzer.__init__(self)
        self.path = path
        self.signals = self.Signals()

    def run(self):
        """
        Gather sample meta-data in the background.
        """
        logger.debug("Thread start for %r", self.path)
        try:
            file_info = self.get_file_info(self.path)
            self.signals.finished.emit(file_info)
        except (IOError, RuntimeError) as err:
            logger.error("Cannot load %r: %s", str(self.path), err)
            self.signals.error.emit(err)
        logger.debug("Thread complete for %r", self.path)

    class Signals(QObject):
        finished = Signal(dict)
        error = Signal(str)

class AsyncFileAnalyzer(QObject):
    def __init__(self):
        QObject.__init__(self)
        self.threadpool = QThreadPool()
        self._waiting_for_info = {}
        self._cache = LRUCache(maxsize=10)

    def request_waveform(self, path, callback = None):
        if isinstance(path, FileKey):
            file_key = path
        else:
            file_key = FileKey(path)
        file_info = self._cache.get(file_key)
        if file_info is not None:
            waveform = file_info.get("waveform")
            callback(file_key, waveform)
            return
        def our_callback(path, file_info):
            if file_info:
                waveform = file_info.get("waveform")
                callback(path, waveform)
        self._request_info(path, callback=our_callback)

    def request_file_metadata(self, path, callback = None):
        if isinstance(path, FileKey):
            file_key = path
        else:
            file_key = FileKey(path)
        file_info = self._cache.get(file_key)
        if file_info is not None:
            metadata = Metadata.from_file_info(file_info)
            callback(file_key, metadata)
            return
        def our_callback(path, file_info):
            if file_info:
                metadata = Metadata.from_file_info(file_info)
            else:
                metadata = None
            callback(path, metadata)
        self._request_info(path, callback=our_callback)

    def _request_info(self, file_key, callback):
        logger.debug("File info for %r not known yet", str(file_key))
        waiting_list = self._waiting_for_info.get(file_key)
        if waiting_list:
            logger.debug("Already requested, adding to the waiting list")
            waiting_list.append(callback)
        else:
            worker = FileAnalyzerWorker(file_key)
            our_callback = partial(self._file_info_received, file_key)
            our_error_callback = partial(self._file_info_error, file_key)
            self._waiting_for_info[file_key] = [callback]
            worker.signals.finished.connect(our_callback)
            worker.signals.error.connect(our_error_callback)
            self.threadpool.start(worker)

    def _file_info_received(self, file_key, file_info):
        logger.debug("file_info_received for %r called with %r", file_key, file_info)
        self._cache.put(file_key, file_info)
        callbacks = self._waiting_for_info.pop(file_key)
        for callback in callbacks:
            callback(file_key, file_info)

    def _file_info_error(self, file_key, err):
        logger.debug("file_info_error for %r called with %r", file_key, err)
        callbacks = self._waiting_for_info.pop(file_key)
        for callback in callbacks:
            callback(file_key, None)

    def get_file_info(self, path):
        if not isinstance(path, FileKey):
            path = FileKey(path)
        return self._cache.get(path)

    def get_file_metadata(self, path):
        file_info = self.get_file_info(path)
        if file_info is not None:
            return Metadata.from_file_info(file_info)
        else:
            return None
