
import os
import logging
import shutil
import sqlite3

from .samplemetadata import FIXED_METADATA

logger = logging.getLogger("library")

from . import __path__ as PKG_PATH
SCHEMA_FILENAME = os.path.join(PKG_PATH[0], "schema.sql")

class LibraryError(Exception):
    pass

class LibraryConflictError(LibraryError):
    pass

DATABASE_VERSION = 0

class Library:
    def __init__(self, app):
        self.db = None
        self.app = app
        self.base_path = os.path.join(app.appdirs.user_data_dir,
                                      "library")
        db_path = os.path.join(self.base_path, "database.db")
        if os.path.exists(db_path):
            self.open_database(db_path)
        else:
            self.create_database(db_path)

    def create_database(self, db_path):
        os.makedirs(self.base_path, exist_ok=True)
        if os.path.exists(db_path):
            # safety check
            raise RuntimeError("{!r} exists while not expected.".format(db_path))
        try:
            try:
                logging.info("Creating new database %r", db_path)
                db = sqlite3.connect(db_path)
                db.executescript(open(SCHEMA_FILENAME).read())
                db.execute("INSERT INTO db_meta(id, version) VALUES (1, ?)",
                           (DATABASE_VERSION,))
                db.commit()
            except sqlite3.Error as err:
                logger.error("Cannot open database %r: %s", db_path, err)
                self.app.exit(1)
        except:
            try:
                os.unlink(db_path)
            except IOError:
                pass
            raise
        self.db = db

    def open_database(self, db_path):
        logging.info("Opening database %r", db_path)
        try:
            db = sqlite3.connect(db_path)
            cur = db.cursor()
            cur.execute("SELECT version FROM db_meta WHERE id=1")
            db.commit()
            row = cur.fetchone()
        except sqlite3.Error as err:
            logger.error("Cannot open database %r: %s", db_path, err)
            self.app.exit(1)
        if not row:
            logging.error("Invalid database: not db_meta data")
            self.app.exit(1)
        version = row[0]
        if version != DATABASE_VERSION:
            logging.error("Invalid database version: %i (%i expected)",
                          version, DATABASE_VERSION)
            self.app.exit(1)
        self.db = db

    def get_library_object_path(self, metadata):
        md5 = metadata["_md5"]
        ext = metadata.get("_format")
        if ext:
            ext = "." + ext.lower()
        else:
            ext = ".bin"
        return os.path.join(self.base_path, md5[0], md5[1:3], md5 + ext)

    def import_file(self, metadata, copy=True):
        if "_md5" not in metadata or "_path" not in metadata:
            raise ValueError("md5 and path are required for file import")
        path = metadata["_path"]
        with self.db:
            cur = self.db.cursor()
            cur.execute("SELECT id FROM items WHERE md5=? LIMIT 1",
                        (metadata["_md5"],))
            if cur.fetchone() is not None:
                raise LibraryConflictError("Already there")
            metadata = metadata.copy()
            if copy:
                metadata["_path"] = None
            metadata["_source"] = "file:{}".format(path)
            query = "INSERT INTO items({}) VALUES ({})".format(
                    ", ".join(mdtype.name for mdtype in FIXED_METADATA),
                    ", ".join(["?"] * len(FIXED_METADATA)))
            values = [metadata.get("_" + mdtype.name) for mdtype in FIXED_METADATA]
            logging.debug("running: %r with %r", query, values)
            cur.execute(query, values)
            if copy:
                target_path = self.get_library_object_path(metadata)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                shutil.copy(path, target_path)

