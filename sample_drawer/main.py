
import argparse
import logging
import shlex
import sys

import appdirs

from PySide2.QtWidgets import QApplication

from .gui.mainwindow import MainWindow
from .gui.signalhandler import SignalHandler
from .library import Library
from .sampleanalyzer import SampleAnalyzer

APP_NAME = "sampledrawer"
APP_AUTHOR = "Jajcus"

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

        self.library = Library(self)

    def parse_args(self):
        parser = argparse.ArgumentParser(description='Sample Drawer – audio sample browser and organizer.')
        parser.set_defaults(debug_level=logging.INFO)
        parser.add_argument('--root', action='store', dest='root',
                            help='Display only this directory in filesystem browser')
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
        self.args = parser.parse_args()

    def setup_logging(self):
        logging.basicConfig(level=self.args.debug_level)

    def import_files(self):
        analyzer = SampleAnalyzer()
        for path in self.args.import_files:
            metadata = analyzer.get_file_metadata(path)
            logging.info(metadata)
            self.library.import_file(metadata)

    def start(self):
        if self.args.import_files:
            return self.import_files()
        self.main_window = MainWindow(self.args)
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
