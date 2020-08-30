
import logging
import os
import re
import shutil

from .metadata import Metadata

TMPDIR_RE = re.compile(r"tmp.(\d+)$")
FILENAME_RE = re.compile(r"([0-9a-f]{32})\.(\w+)$")
HEX_DIGITS = "0123456789abcdef"

logger = logging.getLogger("library_verifier")


class Progress:
    def __init__(self, stages):
        self.stages = stages
        self.stage = 0
        self.stage_name = None
        self.stage_percent = 0
        self.error = None
        self.question = None
        self._saved_answers = {}

    def __repr__(self):
        return "<Progress {}/{} {:3d} {!r} {!r}>".format(self.stage,
                                                         self.stages,
                                                         self.stage_percent,
                                                         self.stage_name,
                                                         self.error)

    def _next_stage(self, name):
        self.stage += 1
        self.stage_name = name
        self.stage_percent = 0
        yield self

    def _set_percent(self, percent):
        logger.debug("_set_percent(%r)", percent)
        if percent < 0:
            percent = 0
        elif percent > 100:
            percent = 100
        else:
            percent = int(percent)
        if percent > self.stage_percent:
            self.stage_percent = percent
            yield self

    def _send_error(self, message, question=None):
        self.error = message
        if question:
            answer = self._saved_answers.get(type(question))
            if answer is not None:
                question.answer(answer)
            else:
                self.question = question
        yield self
        if question and question.save_answer:
            self._saved_answers[type(question)] = question.the_answer
        self.error = None
        self.question = None

    def _clear_error(self):
        self.error = None
        yield self


class Question:
    options = ["Yes", "No"]
    save_options = {"Always": "Yes", "Never": "No"}
    default = "No"
    keys = {"y": "Yes", "n": "No", "a": "Always", "e": "Never"}

    def __init__(self, question):
        self.question = question
        self.the_answer = None
        self.save_answer = False

    @property
    def all_options(self):
        return list(self.options) + list(self.save_options)

    def answer(self, the_answer):
        if the_answer in self.options:
            self.the_answer = the_answer
            self.save_answer = False
        else:
            try:
                the_answer = self.save_options[the_answer]
            except KeyError:
                raise ValueError("Invalid answer")
            self.the_answer = the_answer
            self.save_answer = True


class RemoveItemWhenFileMissing(Question):
    def __init__(self, item_name, path):
        question = "Remove {!r}?".format(item_name)
        Question.__init__(self, question)


class RemoveStaleTmpDir(Question):
    def __init__(self):
        question = "Remove stale temporary directory?"
        Question.__init__(self, question)


class RemoveUnknownFile(Question):
    def __init__(self):
        question = "Remove unknown file?"
        Question.__init__(self, question)


class RemoveInvalidItem(Question):
    def __init__(self):
        question = "Remove invalid item?"
        Question.__init__(self, question)


class FixBrokenTagAssignments(Question):
    def __init__(self, assignments):
        question = "Fix broken tag assignments?"
        Question.__init__(self, question)


class LibraryVerifier:
    def __init__(self, app):
        self.app = app
        self.lib = app.library

    def verify(self):
        progress = Progress(3)
        with self.lib.db as db:
            db.execute("BEGIN EXCLUSIVE TRANSACTION")
            yield from self._check_items(db, progress)
            yield from self._check_files(db, progress)
            yield from self._check_item_tags(db, progress)

    def _check_items(self, db, progress):
        yield from progress._next_stage("Checking items")
        cur = db.execute("SELECT item_count FROM tags WHERE name = '/'")
        row = cur.fetchone()
        if cur:
            item_count = row[0]
        else:
            yield from progress._send_error("Missing '/' tag for total item count")
            cur = db.execute("SELECT COUNT(id) FROM items")
            item_count = cur.fetchone()[0]

        cur = db.execute("SELECT id, name, md5, path, format"
                         " FROM items"
                         " WHERE workplace_id IS NULL")
        i = 0
        to_delete = []
        while True:
            row = cur.fetchone()
            if row is None:
                break
            item_id, name, item_md5, path, file_format = row
            i += 1
            if not (i % 100):
                yield from progress._set_percent(100 * i / item_count)
            metadata = Metadata({"_md5": item_md5,
                                 "_path": path,
                                 "_format": file_format})
            path = self.lib.get_library_object_path(metadata)
            if not os.path.exists(path):
                question = RemoveItemWhenFileMissing(name, path)
                yield from progress._send_error("Item #{} {!r} – file {!r} missing"
                                                .format(item_id, name, path),
                                                question)
                if question.the_answer == "Yes":
                    to_delete.append(item_id)
        if item_count != i:
            yield from progress._send_error("Item counter is wrong says: {} instead on {}"
                                            .format(item_count, i))
        for i in range(0, len(to_delete), 10):
            ids = to_delete[i:i+10]
            logger.debug("Removing items %r", ids)
            placeholders = ", ".join(["?"] * len(ids))
            db.execute("DELETE FROM items WHERE id IN ({})".format(placeholders),
                       ids)
        yield from progress._set_percent(100)

    def _check_files(self, db, progress):
        yield from progress._next_stage("Checking files")
        base_path = self.lib.base_path
        for filename in sorted(os.listdir(base_path)):
            path = os.path.join(base_path, filename)
            if os.path.isfile(path):
                if filename not in ("database.db", "database.db-journal"):
                    logger.warning("Unexpected file: %r", path)
            elif os.path.isdir(path):
                if len(filename) == 1 and filename in HEX_DIGITS:
                    yield from self._check_files2(db, progress, filename)
                else:
                    match = TMPDIR_RE.match(filename)
                    if match:
                        pid = int(match.group(1))
                        if pid != os.getpid():
                            question = RemoveStaleTmpDir()
                            msg = "Unexpected (stale?) temporary directory: "
                            msg += repr(path)
                            yield from progress._send_error(msg, question)
                            if question.the_answer == "Yes":
                                try:
                                    shutil.rmtree(path)
                                except OSError as err:
                                    logger.error("Could not remove %r: %s",
                                                 path, err)
                    else:
                        logger.warning("Unexpected directory: %r", path)
            else:
                logger.warning("Unexpected special file: %r", path)
        yield from progress._set_percent(100)

    def _check_files2(self, db, progress, subdir):
        base_path = self.lib.base_path
        dir_path = os.path.join(base_path, subdir)
        for filename in sorted(os.listdir(dir_path)):
            path = os.path.join(dir_path, filename)
            if os.path.isdir(path):
                if len(filename) == 2:
                    try:
                        number = int(subdir + filename, 16)
                    except ValueError:
                        logger.warning("Unexpected directory: %r", path)
                    else:
                        yield from progress._set_percent(100 * number / 0x1000)
                        yield from self._check_files3(db, progress, subdir, filename)
                else:
                    logger.warning("Unexpected directory: %r", path)
            else:
                logger.warning("Unexpected file: %r", path)

    def _check_files3(self, db, progress, subdir, subdir2):
        analyzer = self.app.analyzer
        base_path = self.lib.base_path
        dir_path = os.path.join(base_path, subdir, subdir2)
        for filename in os.listdir(dir_path):
            path = os.path.join(dir_path, filename)
            if os.path.isdir(path):
                logger.warning("Unexpected directory: %r", path)
                continue
            if not os.path.isfile(path):
                logger.warning("Unexpected special file: %r", path)
                continue
            match = FILENAME_RE.match(filename)
            if not match:
                logger.warning("Unexpected file (bad filename): %r", path)
                continue
            md5 = match.group(1)
            ext = match.group(2)
            if md5[0] != subdir or md5[1:3] != subdir2:
                logger.warning("Unexpected (misplaced) file: %r", path)
                continue
            cur = db.execute("SELECT id, format, path FROM items"
                             " WHERE md5 = ?", (md5,))
            row = cur.fetchone()
            if not row:
                question = RemoveUnknownFile()
                msg = "File {!r} not in the database".format(path)
                yield from progress._send_error(msg, question)
                if question.the_answer == "Yes":
                    try:
                        os.unlink(path)
                    except OSError as err:
                        logger.error("Cannot remove %r: %s", path, err)
                continue
            try:
                file_info = analyzer.get_file_info(path)
            except (OSError, RuntimeError) as err:
                logger.error("Cannot read file %r: %s", path, err)
                file_info = None
            item_id, item_format, item_path = row
            if file_info is None or file_info["md5"] != md5:
                question = RemoveInvalidItem()
                if file_info:
                    msg = "File {!r} checksum mismatch".format(path)
                else:
                    msg = "File {!r} unreadable".format(path)
                yield from progress._send_error(msg, question)
                if question.the_answer == "Yes":
                    try:
                        os.unlink(path)
                    except OSError as err:
                        logger.error("Cannot remove %r: %s", path, err)
                    else:
                        db.execute("DELETE FROM items WHERE id = ?", (item_id,))
            if ext != item_format.lower():
                question = RemoveUnknownFile()
                msg = ("File {!r} extension does not match file format from the library {!r}"
                       .format(path, item_format))
                yield from progress._send_error(msg, question)
                if question.the_answer == "Yes":
                    try:
                        os.unlink(path)
                    except OSError as err:
                        logger.error("Cannot remove %r: %s", path, err)
                continue

            # TODO: check format/duration/etc
            # it is hard to imagine a mismatch here would happen, though

    def _check_item_tags(self, db, progress):
        yield from progress._next_stage("Checking item tags")
        cur = db.execute("SELECT id, tag_id, item_id FROM item_tags"
                         " WHERE tag_id NOT IN (SELECT id FROM tags)")
        rows = cur.fetchall()
        missing_tags = set([row[1] for row in rows])
        yield from progress._set_percent(50)
        if missing_tags:
            question = FixBrokenTagAssignments(rows)
            yield from progress._send_error("Missing item tags: {!r}"
                                            .format(missing_tags),
                                            question)
            if question.the_answer == "Yes":
                db.execute("DELETE FROM item_tags"
                           " WHERE tag_id NOT IN (SELECT id FROM tags)")
        cur = db.execute("SELECT id, item_id FROM item_tags"
                         " WHERE item_id NOT IN (SELECT id FROM items)")
        rows = cur.fetchall()
        missing_items = set([row[1] for row in rows])
        yield from progress._set_percent(100)
        if missing_items:
            question = FixBrokenTagAssignments(rows)
            yield from progress._send_error("Missing tag items: {!r}"
                                            .format(missing_items),
                                            question)
            if question.the_answer == "Yes":
                db.execute("DELETE FROM item_tags"
                           " WHERE item_id NOT IN (SELECT id FROM items)")
