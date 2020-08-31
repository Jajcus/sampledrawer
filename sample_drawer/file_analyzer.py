
import hashlib
import os
import logging

try:
    from functools import cached_property
except ImportError:
    cached_property = property

from soundfile import SoundFile

from .dsp import compute_peak_level, compute_waveform
from .lru_cache import LRUCache
from .metadata import Metadata

READ_BLOCK_SIZE = 16*1024*1024

logger = logging.getLogger("file_analyzer")


class FileKey:
    """For reliably using filenames as keys in a cache.

    When hashed for the first time (e.g. used as a dictionary key) file stat will be checked
    and used together with the absolute path for hashing and comparison. This
    way a file modified on disk won't be considered to be the same as the one
    stored in cache.
    """

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

        return hash(self.path)

    def __eq__(self, other):
        if isinstance(other, FileKey):
            return (self.path == other.path
                    and self.stat
                    and self.stat.st_size == other.stat.st_size
                    and self.stat.st_mtime == other.stat.st_mtime)

        return self.path == other


class FileAnalyzer:
    def __init__(self):
        pass

    def get_file_info(self, path):
        file_info = {"path": str(path)}
        logger.debug("Analyzing %r...", path)
        with open(str(path), "rb") as source_file:
            with SoundFile(source_file) as snd_file:
                samplerate = snd_file.samplerate
                logger.debug("samplerate: %r", samplerate)
                file_info["sample_rate"] = samplerate
                total_frames = snd_file.frames
                logger.debug("frames: %r", total_frames)
                file_info["duration"] = total_frames / samplerate
                channels = snd_file.channels
                logger.debug("channels: %r", channels)
                file_info["channels"] = channels
                logger.debug("format: %r", snd_file.format)
                file_info["format"] = snd_file.format
                logger.debug("subtype: %r", snd_file.subtype)
                file_info["format_subtype"] = snd_file.subtype

                frames = snd_file.read(always_2d=True)
                frames_read = len(frames)

                logger.debug("frames: %r", frames)
                logger.debug("%r frames read", frames_read)

                try:
                    file_info["peak_level"] = compute_peak_level(frames)
                except ValueError as err:
                    logger.error(str(err))

                file_info["waveform"] = compute_waveform(frames, samplerate)

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
        return Metadata.from_file_info(file_info)


class CachedFileAnalyzer(FileAnalyzer):
    def __init__(self):
        self._cache = LRUCache()

    def get_file_info(self, path):
        if not isinstance(path, FileKey):
            path = FileKey(path)
        file_info = self._cache.get(path)
        if file_info is None:
            file_info = super().get_file_info(path)
        return file_info
