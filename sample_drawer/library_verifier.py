
import os

from .library import Library
from .metadata import Metadata

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
    def __init__(self, question, options=["Yes", "No"], default="No",
                 save_options={"Always": "Yes", "Never": "No"}):
        self.question = question
        self.options = options
        self.default = default
        self.save_options = save_options
        self.the_answer = None
        self.save_answer = False
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
    def get_option_keys(self):
        all_options = list(self.options) + list(self.save_options)
        result = {}
        for option in all_options:
            for c in option:
                if c.isupper():
                    if option == self.default:
                        key = c
                    else:
                        key = c.lower()
                    if key not in result:
                        result[key] = option
                        break
        return result

class RemoveItemWhenFileMissing(Question):
    def __init__(self, item_name, path):
        question = "Remove {!r}?".format(item_name)
        Question.__init__(self, question)


class LibraryVerifier:
    def __init__(self, library):
        self.lib = library
    def verify(self):
        progress = Progress(1)
        with self.lib.db as db:
            db.execute("BEGIN EXCLUSIVE TRANSACTION")
            yield from self._check_items(db, progress)
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
                         " WHERE scratchpad_id IS NULL")
        i = 0
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

        yield from progress._set_percent(100)
