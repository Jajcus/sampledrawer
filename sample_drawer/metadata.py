
import logging
import os
import re

from collections import namedtuple, defaultdict

MDType = namedtuple("MDType",
                    "name type editable unit indexable",
                    defaults=(False, None, True),
                    )

FIXED_METADATA = [
    MDType(name="md5", type=str, indexable=False),
    MDType(name="path", type=str, indexable=False),
    MDType(name="source", type=str, indexable=False),
    MDType(name="name", type=str, editable=True),
    MDType(name="format", type=str),
    MDType(name="format_subtype", type=str),
    MDType(name="sample_rate", type=int, unit="frames/s"),
    MDType(name="channels", type=int, indexable=False),
    MDType(name="duration", type=float, unit="s"),
    MDType(name="peak_level", type=float, unit="dBFS"),
]
FIXED_METADATA_D = {mdtype.name: mdtype for mdtype in FIXED_METADATA}
FIXED_METADATA_KEYS = {"_" + mdtype.name: mdtype for mdtype in FIXED_METADATA}

VALID_KEY_RE = re.compile(r"^[^\W_][\w -]+$")
VALID_TAG_RE = re.compile(r"^((/[\w-]+)*/)?[\w-]+$")

INVALID_TAG_CHAR = re.compile(r"[^\w/-]")

logger = logging.getLogger("metadata")


class Metadata:
    def __init__(self, data=None, tags=None):
        object.__setattr__(self, "_data", {})
        object.__setattr__(self, "_tags", set())
        if data is not None:
            for key, value in data.items():
                mdtype = FIXED_METADATA_KEYS.get(key)
                if mdtype:
                    if value is not None:
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
            for tag in tags:
                if not VALID_TAG_RE.match(tag):
                    logger.warning("Invalid tag: %r", key)
                else:
                    self._tags.add(tag)

    def __repr__(self):
        return "Metadata({!r}, {!r})".format(self._data, self._tags)

    @classmethod
    def from_file_info(cls, file_info):
        data = {"_" + k: v for (k, v) in file_info.items()
                if k in FIXED_METADATA_D}
        return cls(data)

    def copy(self):
        return self.__class__(self._data, self._tags)

    def get_tags(self):
        return set(self._tags)

    def set_tags(self, tags):
        new_tags = set()
        for tag in tags:
            if not VALID_TAG_RE.match(tag):
                logger.warning("Invalid tag: %r", key)
            else:
                new_tags.add(tag)
        object.__setattr__(self, "_tags", new_tags)

    def add_tags(self, tags):
        for tag in tags:
            if not VALID_TAG_RE.match(tag):
                logger.warning("Invalid tag: %r", key)
            else:
                self._tags.add(tag)

    def remove_tags(self, tags):
        for tag in tags:
            if not VALID_TAG_RE.match(tag):
                logger.warning("Invalid tag: %r", key)
            else:
                self._tags.discard(tag)

    def __getattr__(self, key):
        if key in FIXED_METADATA_D:
            return self._data.get("_" + key)

        raise KeyError(key)

    def __setattr__(self, key, value):
        mdtype = FIXED_METADATA_D.get(key)
        if mdtype:
            key = "_" + key
            if value is None:
                try:
                    del self._data[key]
                except KeyError:
                    pass
            else:
                self._data[key] = mdtype.type(value)
        else:
            raise AttributeError("Cannot set {!r}".format(key))

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
            if mdtype and mdtype.type is float:
                value = "{:.2f}".format(value)
            else:
                value = str(value)
            if mdtype and mdtype.unit:
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
        logger.debug("setting %r to %r", key, value)
        self._data[key] = value

    def __contains__(self, key):
        return key in self._data

    def rewrite(self, rules, root=None):
        """Return copy rewriten using given rules.

        Each rule is a tuple: (field, regexp, substitutions)
        Regexp is applied to the value of a given field and if it matches, then
        metadata fields will be changed according to substitutions, which
        are mapping from field name to .format() string, that uses regexp groups
        and current metadata values."""
        data = dict(self._data)
        data["_tags"] = " ".join(self._tags)
        if root:
            logger.debug("Root %r given, auto-generating category", root)
            root = os.path.normpath(root)
            directory = os.path.dirname(self.path)
            if os.path.commonpath([directory, root]) == root:
                relpath = os.path.relpath(directory, root)
                if relpath == ".":
                    logger.debug("no category in path")
                else:
                    if os.path.sep != "/":
                        relpath = relpath.replace(os.path.sep, "/")
                    category = INVALID_TAG_CHAR.sub("_", relpath)
                    data["_auto_category"] = "/" + category
            else:
                logger.debug("%r not under %r", self.path, root)
        for key, regexp, substs in rules:
            value = data.get(key)
            if value is None:
                logging.debug("Ignoring rewrite rule for %r – no value", key)
                continue
            logging.debug("Applying %r to %r=%r", regexp, key, value)
            if isinstance(regexp, str):
                regexp = re.compile(regexp)
            if not isinstance(value, str):
                value = str(value)
            match = regexp.match(value)
            if not match:
                logging.debug("no match")
                continue
            format_list = [match.group(0)] + list(match.groups())
            format_dict = defaultdict(lambda: "", data)
            format_dict.update(match.groupdict())
            for target, pattern in substs.items():
                mdtype = FIXED_METADATA_KEYS.get(target)
                if mdtype:
                    if not mdtype.editable:
                        logging.warning(
                            "%r is not editable, not substituting", target)
                        continue
                logging.debug("setting %r with pattern %r (%r, %r)",
                              target, pattern, format_list, format_dict)
                try:
                    new_value = pattern.format(*format_list, **format_dict)
                except KeyError as err:
                    logging.warning("%r substitution failed: key not found: %r",
                                    pattern, str(err))
                    continue
                except (IndexError, ValueError, TypeError) as err:
                    logging.warning("%r substitution failed: %s", pattern, err)
                    continue
                logging.debug("new value: %r", new_value)
                data[target] = new_value
        try:
            del data["_auto_category"]
        except KeyError:
            pass
        tags = data["_tags"].split()
        del data["_tags"]
        return self.__class__(data, tags)
