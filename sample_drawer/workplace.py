
import os
import logging
import shutil


from .metadata import FIXED_METADATA
from .search import SearchQuery

logger = logging.getLogger("workplace")


class WorkplaceError(Exception):
    def __str__(self):
        return str(self.args[0])


class WorkplaceConflictError(WorkplaceError):
    @property
    def path(self):
        return self.args[1]

    @property
    def existing_name(self):
        return self.args[2]


class Workplace:
    def __init__(self, app, library, name):
        self.tmp_dir = None
        self.id = None
        self.name = name
        self.app = app
        self.library = library
        self.base_path = os.path.join(app.appdirs.user_data_dir,
                                      "workplaces", name)
        with self.library.db as dbconn:
            cur = dbconn.cursor()
            cur.execute("SELECT id FROM workplaces WHERE name=?", (name,))
            row = cur.fetchone()
            if row is not None:
                self.id = row[0]
                logger.debug("Found existing workplace: %i", self.id)
            else:
                cur.execute("INSERT INTO workplaces(name) VALUES (?)",
                            (name,))
                self.id = cur.lastrowid
                logger.debug("Creating new workplace: %i", self.id)
        os.makedirs(self.base_path, exist_ok=True)

    def get_item_path(self, metadata):
        logger.debug("get_item_path(%r)", metadata)
        if metadata.path:
            if os.path.isabs(metadata.path):
                local_path = metadata.path
            else:
                local_path = os.path.join(self.base_path, metadata.path)
            if os.path.exists(local_path):
                return local_path
        else:
            local_path = None

        tmp_metadata = metadata.copy()
        tmp_metadata.path = None
        path = self.library.get_item_path(tmp_metadata)
        if os.path.exists(path):
            return path

        source = metadata.source
        if source.startswith("file:"):
            return source[5:]

        return local_path

    def delete_item(self, metadata):
        path = metadata.path
        if os.path.isabs(path):
            return False
        with self.library.db:
            cur = self.library.db.cursor()
            cur.execute("DELETE FROM items"
                        " WHERE path=? AND workplace_id=?",
                        (path, self.id))
            if not cur.rowcount:
                logger.warning("Could not remove %r from workplace database",
                               path)
            else:
                logger.debug("Removed %r from database: %i rows",
                             path, cur.rowcount)
            normpath = os.path.normpath(path)
            if normpath.startswith("/") or normpath.startswith("../"):
                logger.warning("refusing to remove %r – not in the workplace",
                               path)
            full_path = os.path.join(self.base_path, path)
            try:
                os.unlink(full_path)
                logger.debug("Removed %r", full_path)
            except FileNotFoundError as err:
                logger.debug("Not removed %r: %s", full_path, err)
            except OSError as err:
                logger.warning("Could not remove %r: %s", full_path, err)

    def import_file(self, metadata, copy=False, folder="", name=None):
        orig_path = metadata.path
        if not metadata.md5 or not orig_path:
            raise ValueError("md5 and path are required for file import")
        if name is None:
            name = metadata.name
            if not metadata.name:
                name = os.path.basename(orig_path).rsplit(".", 1)[0]
        source = "file:{}".format(orig_path)
        with self.library.db:
            path = self._import_item(source, metadata, folder, name)
            if copy:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                shutil.copy(orig_path, path)

    def import_item(self, metadata, copy=False, folder="", name=None):
        if not metadata.md5:
            raise ValueError("md5 is required for lib item import")
        if name is None:
            name = metadata.name
        source = "lib:{}".format(metadata.md5)
        with self.library.db:
            path = self._import_item(source, metadata, folder, name)
            if copy:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                shutil.copy(self.library.get_item_path(metadata),
                            path)

    def _import_item(self, source, metadata, folder="", name=None):
        if metadata.format:
            filename = "{}.{}".format(name, metadata.format.lower())
        else:
            filename = "{}.bin".format(name)
        path = os.path.join(folder, filename)
        cur = self.library.db.cursor()
        cur.execute("SELECT id, name, md5"
                    " FROM items"
                    " WHERE path=? AND workplace_id=?"
                    " LIMIT 1", (path, self.id))
        row = cur.fetchone()
        if row is not None:
            raise WorkplaceConflictError("Already there", path, row[1])
        metadata = metadata.copy()
        metadata.path = path
        metadata.name = name
        metadata.source = source
        query = "INSERT INTO items(workplace_id,{}) VALUES ({})".format(
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
            cur.execute("INSERT INTO item_tags(item_id, tag_id) VALUES(?, ?)",
                        (item_id, tag_id))

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
                        " VALUES(?, ?, ?)",
                        (item_id, key_id, value))

    def get_items(self):
        query = SearchQuery([])
        query, params = query.as_sql(workplace_id=self.id)
        result = []
        with self.library.db:
            cur = self.library.db.cursor()
            logging.debug("running: %r with %r", query, params)
            cur.execute(query, params)
            for row in cur.fetchall():
                result.append(self.library._metadata_from_row(row))
        return result
