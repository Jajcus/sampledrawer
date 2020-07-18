
import os
import logging
import sqlite3

logger = logging.getLogger("library")

from . import __path__ as PKG_PATH
SCHEMA_FILENAME = os.path.join(PKG_PATH[0], "schema.sql")

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

