
import os
import logging
import shutil
import sqlite3
import threading

from collections import defaultdict

from .metadata import FIXED_METADATA, FIXED_METADATA_D, FIXED_METADATA_KEYS, Metadata
from .search import SearchQuery

logger = logging.getLogger("scratchpad")

class ScratchpadError(Exception):
    def __str__(self):
        return str(self.args[0])

class ScratchpadConflictError(ScratchpadError):
    @property
    def path(self):
        return self.args[1]
    @property
    def existing_name(self):
        return self.args[2]

class Scratchpad:
    def __init__(self, app, library, name):
        self.tmp_dir = None
        self.id = None
        self.name = name
        self.app = app
        self.library = library
        self.base_path = os.path.join(app.appdirs.user_data_dir,
                                      "scratchpads", name)
        with self.library.db as dbconn:
            cur = dbconn.cursor()
            cur.execute("SELECT id FROM scratchpads WHERE name=?", (name,))
            row = cur.fetchone()
            if row is not None:
                self.id = row[0]
                logger.debug("Found existing scratchpad: %i", self.id)
            else:
                cur.execute("INSERT INTO scratchpads(name) VALUES (?)",
                            (name,))
                self.id = cur.lastrowid
                logger.debug("Creating new scratchpad: %i", self.id)
        os.makedirs(self.base_path, exist_ok=True)

    def get_object_path(self, metadata):
        logger.debug("get_object_path(%r)", metadata)
        if metadata.path:
            if os.path.isabs(metadata.path):
                local_path = metadata.path
            else:
                local_path = os.path.join(self.base_path, metadata.path)
            if os.path.exists(local_path):
                return local_path
        else:
            local_path = None
        source = metadata.source
        if source.startswith("file:"):
            return source[5:]
        elif source.startswith("library:"):
            tmp_metadata = metadata.copy()
            tmp_metadata.md5 = source[8:]
            return self.library.get_library_object_path(tmp_metadata)
        return local_path

    def import_file(self, metadata, copy=False, folder="", name=None):
        md5 = metadata.md5
        orig_path = metadata.path
        if not md5 or not orig_path:
            raise ValueError("md5 and path are required for file import")
        if name is None:
            name = metadata.name
            if not metadata.name:
                name = os.path.basename(orig_path).rsplit(".", 1)[0]
        if metadata.format:
            filename = "{}.{}".format(name, metadata.format.lower())
        else:
            filename = "{}.bin".format(name)
        path = os.path.join(folder, filename)
        with self.library.db:
            cur = self.library.db.cursor()
            cur.execute("SELECT id, name, md5"
                        " FROM items"
                        " WHERE path=?"
                        " LIMIT 1", (path,))
            row = cur.fetchone()
            if row is not None:
                raise ScratchpadConflictError("Already there", path, row[1])
            metadata = metadata.copy()
            metadata.path = path
            metadata.name = name
            metadata.source = "file:{}".format(orig_path)
            query = "INSERT INTO items(scratchpad_id,{}) VALUES ({})".format(
                    ", ".join(mdtype.name for mdtype in FIXED_METADATA),
                    ", ".join(["?"] * (len(FIXED_METADATA) + 1)))
            values = [self.id] + [getattr(metadata, mdtype.name)
                                  for mdtype in FIXED_METADATA]
            logging.debug("running: %r with %r", query, values)
            cur.execute(query, values)
            item_id = cur.lastrowid
            logging.debug("item inserted with id: %r", item_id)
            tags = metadata.get_tags()

            # add missing parent tags
            # as  /a/b/c implies /a/b and /a
            for tag in list(tags):
                if tag.startswith("/"):
                    parent = tag.rsplit("/", 1)[0]
                    while parent:
                        tags.add(parent)
                        parent = parent.rsplit("/", 1)[0]

            for tag in tags:
                cur.execute("SELECT id FROM tags WHERE name=?", (tag,))
                row = cur.fetchone()
                if row:
                    tag_id = row[0]
                else:
                    cur.execute("INSERT INTO tags(name) VALUES(?)", (tag,))
                    tag_id = cur.lastrowid
                cur.execute("INSERT INTO item_tags(item_id, tag_id)"
                                " VALUES(?, ?)", (item_id, tag_id))

            for key in metadata:
                if key.startswith("_"):
                    continue
                value = metadata[key]
                cur.execute("SELECT id FROM custom_keys WHERE name=?", (key,))
                row = cur.fetchone()
                if row:
                    key_id = row[0]
                else:
                    cur.execute("INSERT INTO custom_keys(name) VALUES(?)", (key,))
                    key_id = cur.lastrowid
                cur.execute("INSERT INTO item_custom_values(item_id, key_id, value)"
                                " VALUES(?, ?, ?)", (item_id, key_id, value))

            if copy:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                shutil.copy(orig_path, path)

    def get_items(self):
        query = SearchQuery([])
        query, params = query.as_sql(scratchpad_id=self.id)
        result = []
        with self.library.db:
            cur = self.library.db.cursor()
            logging.debug("running: %r with %r", query, params)
            cur.execute(query, params)
            for row in cur.fetchall():
                result.append(self.library._metadata_from_row(row))
        return result
