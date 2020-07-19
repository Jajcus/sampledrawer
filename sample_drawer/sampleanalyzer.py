
import hashlib
import math
import os
import logging

from functools import cached_property

from soundfile import SoundFile
import numpy

from .lrucache import LRUCache
from .samplemetadata import SampleMetadata

WAVEFORM_RESOLUTION = 200 # samples per second

READ_BLOCK_SIZE = 16*1024*1024

logger = logging.getLogger("sampleanalyzer")

class FileKey:
    """For reliably using filenames as keys in a cache."""
    def __init__(self, path):
        if isinstance(path, FileKey):
            self.path = path.path
            self.stat = path.stat
        else:
            self.path = os.path.realpath(path)
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

class SampleAnalyzer:
    def __init__(self):
        pass

    def get_file_info(self, path):
        file_info = { "path": str(path) }
        with open(str(path), "rb") as source_file:
            with SoundFile(source_file) as snd_file:
                logger.debug("name: %r", snd_file.name)
                logger.debug("mode: %r", snd_file.mode)
                logger.debug("samplerate: %r", snd_file.samplerate)
                file_info["sample_rate"] = snd_file.samplerate
                logger.debug("frames: %r", snd_file.frames)
                file_info["duration"] = float(snd_file.frames) / snd_file.samplerate
                logger.debug("channels: %r", snd_file.channels)
                file_info["channels"] = snd_file.channels
                logger.debug("format: %r", snd_file.format)
                file_info["format"] = snd_file.format
                logger.debug("subtype: %r", snd_file.subtype)
                file_info["format_subtype"] = snd_file.subtype
                logger.debug("endian: %r", snd_file.endian)
                logger.debug("format_info: %r", snd_file.format_info)
                logger.debug("subtype_info: %r", snd_file.subtype_info)
                logger.debug("sections: %r", snd_file.sections)
                logger.debug("closed: %r", snd_file.closed)
                logger.debug("extra_info: %r", snd_file.extra_info)
                frames = snd_file.read()
                peak_level = max(numpy.amax(frames), -numpy.amin(frames))
                if not peak_level:
                    peak_level_db = -math.inf
                    file_info["peak_level"] = peak_level_db
                else:
                    try:
                        peak_level_db = 20*math.log10(peak_level)
                        file_info["peak_level"] = peak_level_db
                    except ValueError:
                        logger.error("Cannot convert %r to dBFS", peak_level)
                logger.debug("%r frames read", len(frames))
            source_file.seek(0)
            md5_hash = hashlib.md5()
            while True:
                data = source_file.read(READ_BLOCK_SIZE)
                if not data:
                    break
                md5_hash.update(data)
            file_info["md5"] = md5_hash.hexdigest()
        return file_info

    def get_file_metadata(self, path):
        file_info = self.get_file_info(path)
        return SampleMetadata.from_file_info(file_info)

class CachedSampleAnalyzer(SampleAnalyzer):
    def __init__(self):
        self._cache = LRUCache(maxsize=10)

    def get_file_info(self, path):
        if not isinstance(path, FileKey):
            path = FileKey(path)
        file_info = self._cache.get(path)
        if file_info is None:
            file_info = super().get_file_info(path)
        return file_info
