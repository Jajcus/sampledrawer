
import argparse
import logging
import os
import shlex
import sys

import appdirs

from .gui.app import GUIApplication
from .library import Library, LibraryConflictError
from .library_verifier import LibraryVerifier
from .scratchpad import Scratchpad
from .file_analyzer import FileAnalyzer
from .metadata import FIXED_METADATA_D, FIXED_METADATA_KEYS, VALID_KEY_RE

APP_NAME = "sampledrawer"
APP_AUTHOR = "Jajcus"

DEFAULT_IMPORT_RULES = [
        ("_path", r"^(.*/)?([^/]*?)(\.[^/.]*)?$", {"_name": "{2}"}),
        ("_auto_category", r"^/.*$", {"_tags": "{_tags} {0}"}),
        ]

LOG_FORMAT = "%(asctime)-15s %(message)s"

logger = logging.getLogger("main")

def metadata_key_value(arg):
    if "=" not in arg:
        raise argparse.ArgumentTypeError("'=' missing")
    key, value = arg.split("=", 1)
    if key.startswith("_"):
        # explicit fixed metadata reference
        try:
            key = FIXED_METADATA_KEYS[key]
        except KeyError:
            raise argparse.ArgumentTypeError("{!r} is not a valid key".format(key))
    else:
        mdtype = FIXED_METADATA_D.get(key)
    if mdtype:
        if not mdtype.editable:
            raise argparse.ArgumentTypeError("{!r} is not editable".format(key))
        key = "_" + mdtype.name
    return (key.lower(), value)

class Application:
    def __init__(self):
        self.args = None
        self.main_window = None
        self.library = None
        self.gui = None
        self.appdirs = appdirs.AppDirs(APP_NAME, APP_AUTHOR)

        self.parse_args()
        self.setup_logging()

        self.analyzer = FileAnalyzer()
        self.library = Library(self)
        self.scratchpad = Scratchpad(self, self.library, self.args.scratchpad)

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Sample Drawer – audio sample browser and organizer.')
        parser.set_defaults(debug_level=logging.INFO, metadata=[])
        parser.add_argument('--root', action='store', dest='root',
                            help='For GUI: Display only this directory in filesystem browser'
                            ' For import: root for automatic categorization')
        parser.add_argument('--debug', action='store_const',
                            dest='debug_level', const=logging.DEBUG,
                            help='Enable debug output')
        parser.add_argument('--quiet', action='store_const',
                            dest='debug_level', const=logging.ERROR,
                            help='Show only errors')
        parser.add_argument('--qt-options', type=shlex.split, action='extend',
                            dest='qt_argv', default=[sys.argv[0]],
                            help='Command line options to pass to the Qt library')
        parser.add_argument('--import', nargs="+", metavar="PATH",
                            dest="import_files",
                            help='Import files to the library')
        parser.add_argument('--tag', action="append", dest='tags',
                            help='Tag to select or add')
        parser.add_argument('--set', action="append", dest='metadata',
                            metavar='KEY=VALUE', type=metadata_key_value,
                            help='Set custom metadata')
        parser.add_argument('--scratchpad', default="main",
                            help='Select scratchpad to use')
        parser.add_argument('--check-db', action="store_true",
                            help='Verify library database consistency')
        self.args = parser.parse_args()

    def setup_logging(self):
        logging.basicConfig(level=self.args.debug_level,
                            format=LOG_FORMAT)

    def check_db(self):
        verifier = LibraryVerifier(self)
        last_stage = 0
        last_percent = -10
        errors = 0
        for progress in verifier.verify():
            logger.debug("verify progress: %r", progress)
            stage = progress.stage
            if stage != last_stage:
                logger.info("=== [%i/%i] %s ===", stage, progress.stages,
                            progress.stage_name)
                last_percent = -10
            last_stage = stage
            percent = progress.stage_percent
            if (percent - last_percent) > 10 and (
                    percent != 100 or last_percent > 0):
                # show percent change only if it didn't go to 100% immediately
                logger.info("%3i%%%s", percent, "..." if percent < 100 else "")
                last_percent = percent
            if progress.error:
                logger.error("%s", progress.error)
                errors += 1
            question = progress.question
            if question:
                options = []
                keys = []
                for key, option in question.keys.items():
                    if options == question.default:
                        keys.append(key.upper())
                    else:
                        keys.append(key)
                prompt = "{} [{}] ".format(question.question, "/".join(keys))
                while True:
                    answer = input(prompt)
                    if not answer:
                        if question.default:
                            answer = question.default
                        else:
                            continue
                    elif answer in question.all_options:
                        break
                    else:
                        try:
                            answer = question.keys[answer]
                            break
                        except KeyError:
                            continue
                question.answer(answer)
        if errors:
            return 1
        else:
            return 0

    def import_file(self, metadata_rules, path, root):
        try:
            metadata = self.analyzer.get_file_metadata(path)
        except (OSError, RuntimeError) as err:
            logger.warning("Cannot import %r: %s", path, err)
            return False
        logger.debug(metadata)
        metadata = metadata.rewrite(metadata_rules, root=root)
        if self.args.tags:
            metadata.add_tags(self.args.tags)
        for key, value in self.args.metadata:
            metadata[key] = value
        try:
            self.library.import_file(metadata)
        except LibraryConflictError as err:
            logger.info("File %r (%r) already in the library, known as %r."
                        " Ignoring it.", path, err.md5, err.existing_name)
            return False
        return True

    def import_dir(self, metadata_rules, path):
        if self.args.root:
            root = self.args.root
        else:
            root = path
        for dirpath, dirnames, filenames in os.walk(path):
            for name in filenames:
                file_path = os.path.join(dirpath, name)
                logger.info("Importing %r", file_path)
                self.import_file(metadata_rules, file_path, root)

    def import_files(self, metadata_rules=DEFAULT_IMPORT_RULES):
        for path in self.args.import_files:
            if os.path.isdir(path):
                self.import_dir(metadata_rules, path)
            else:
                self.import_file(metadata_rules, path, root=self.args.root)

    def start(self):
        if self.args.import_files:
            return self.import_files()
        elif self.args.check_db:
            return self.check_db()
        else:
            self.gui = GUIApplication(self)
            try:
                return self.gui.start()
            finally:
                self.gui = None

    def exit(self, code):
        sys.exit(code)

def main():
    app = Application()
    sys.exit(app.start())
