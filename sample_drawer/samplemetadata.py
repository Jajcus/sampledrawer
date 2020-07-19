
import logging
import re

from collections import namedtuple

MDType = namedtuple("MDType",
                    "name type editable unit",
                    defaults=(False, None),
                    )

FIXED_METADATA = [
        MDType(name="md5", type=str),
        MDType(name="path", type=str),
        MDType(name="source", type=str),
        MDType(name="name", type=str, editable=True),
        MDType(name="format", type=str),
        MDType(name="format_subtype", type=str),
        MDType(name="sample_rate", type=int, unit="frames/s"),
        MDType(name="channels", type=int),
        MDType(name="duration", type=float, unit="s"),
        MDType(name="peak_level", type=float, unit="dBFS"),
        ]
FIXED_METADATA_D = {mdtype.name: mdtype for mdtype in FIXED_METADATA}
FIXED_METADATA_KEYS = {"_" + mdtype.name: mdtype for mdtype in FIXED_METADATA}

VALID_KEY_RE = re.compile(r"^[^\W_][\w -]+$")
VALID_TAG_RE = re.compile(r"^[^\W_][\w-]+(:[^\W_][\w-]+)*$")

logger = logging.getLogger("samplemetadata")

class SampleMetadata:
    def __init__(self, data=None, tags=None):
        self._data = {}
        self._tags = set()
        self._categories = set()
        if data is not None:
            for key, value in data.items():
                mdtype = FIXED_METADATA_KEYS.get(key)
                if mdtype:
                    try:
                        value = mdtype.type(value)
                        self._data[key] = value
                    except (ValueError, TypeError):
                        logging.warning("Invalid %r: %r", key, data[key])
                elif not VALID_KEY_RE.match(key):
                    logger.warning("Invalid meta-data key: %r", key)
                else:
                    self._data[key] = value
        if tags is not None:
            tmp_tags = set()
            for tag in tags:
                if not VALID_TAG_RE.match(tag):
                    logger.warning("Invalid tag: %r", key)
                else:
                    tmp_tags.add(tag)
            self.tags = tmp_tags
            while tmp_tags:
                tmp_tags = {tag.rsplit(":", 1)[0] for tag in tmp_tags if ":" in tag}
                self._categories |= tmp_tags
    def __repr__(self):
        return "SampleMetadata({!r}, {!r})".format(self._data, self._tags)
    @classmethod
    def from_file_info(cls, file_info):
        data = {"_" + k: v for (k, v) in file_info.items() if k in FIXED_METADATA_D}
        return cls(data)
    def copy(self):
        return self.__class__(self._data, self._tags)
    def __iter__(self):
        return iter(self._data)
    def __len__(self):
        return len(self._data)
    def get(self, key, default=None):
        return self._data.get(key, default)
    def get_formatted(self, key, default=None):
        mdtype = FIXED_METADATA_KEYS.get(key)
        value = self._data.get(key, default)
        if value is None:
            value = ""
        else:
            if mdtype.type is float:
                value = "{:.2f}".format(value)
            else:
                value = str(value)
            if mdtype.unit:
                value = "{} {}".format(value, mdtype.unit)
        if key.startswith("_"):
            key = key[1:]
        key = key.capitalize()
        return key, value
    def __getitem__(self, key):
        return self._data[key]
    def __setitem__(self, key, value):
        mdtype = FIXED_METADATA_KEYS.get(key)
        if mdtype:
            if value is not None:
                value = mdtype.type(value)
        elif not VALID_KEY_RE.match(key):
            raise ValueError("Invalid meta-data key: {!r}".format(key))
        self._data[key] = value
    def __contains__(self, key):
        return key in self._data
