
import argparse
import logging
import os
import shlex
import sys

import appdirs

from PySide2.QtWidgets import QApplication

from .gui.main_window import MainWindow
from .gui.signal_handler import SignalHandler
from .library import Library, LibraryConflictError
from .file_analyzer import FileAnalyzer

APP_NAME = "sampledrawer"
APP_AUTHOR = "Jajcus"

DEFAULT_IMPORT_RULES = [
        ("_path", r"^(.*/)?([^/]*?)(\.[^/.]*)?$", {"_name": "{2}"}),
        ("_auto_category", r"^/.*$", {"_tags": "{_tags} {0}"}),
        ]

LOG_FORMAT = "%(asctime)-15s %(message)s"

class Exitting(BaseException):
    """Raised to abort code after Application.exit()"""
    pass

class Application:
    def __init__(self):
        self.args = None
        self.main_window = None
        self.library = None
        self.qapp = None
        self.started = False
        self.appdirs = appdirs.AppDirs(APP_NAME, APP_AUTHOR)

        self.parse_args()
        self.setup_logging()

        logging.debug("qt_argv: %r", self.args.qt_argv)
        self.qapp = QApplication(self.args.qt_argv)

        self.analyzer = FileAnalyzer()
        self.library = Library(self)

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Sample Drawer – audio sample browser and organizer.')
        parser.set_defaults(debug_level=logging.INFO)
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
        self.args = parser.parse_args()

    def setup_logging(self):
        logging.basicConfig(level=self.args.debug_level,
                            format=LOG_FORMAT)

    def import_file(self, metadata_rules, path, root):
        try:
            metadata = self.analyzer.get_file_metadata(path)
        except (OSError, RuntimeError) as err:
            logging.warning("Cannot import %r: %s", path, err)
            return False
        logging.debug(metadata)
        metadata = metadata.rewrite(metadata_rules, root=root)
        if self.args.tags:
            metadata.add_tags(self.args.tags)
        try:
            self.library.import_file(metadata)
        except LibraryConflictError as err:
            logging.info("File %r (%r) already in the library, known as %r."
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
                logging.info("Importing %r", file_path)
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
        self.main_window = MainWindow(self)
        self.main_window.show()
        signal_handler = SignalHandler()
        signal_handler.activate()
        self.qapp.aboutToQuit.connect(signal_handler.deactivate)
        self.started = True
        try:
            return self.qapp.exec_()
        except Exitting:
            pass
        finally:
            self.started = False

    def exit(self, code):
        if self.qapp and self.started:
            self.qapp.exit(code)
        else:
            sys.exit(code)

def main():
    app = Application()
    sys.exit(app.start())
