
import argparse
import logging
import sys

from PySide2.QtWidgets import QApplication

from .mainwindow import MainWindow
from .signalhandler import SignalHandler

def main():
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
    args = parser.parse_args()

    logging.basicConfig(level=args.debug_level)
    app = QApplication([])
    win = MainWindow(args)
    win.show()
    signal_handler = SignalHandler()
    signal_handler.activate()
    app.aboutToQuit.connect(signal_handler.deactivate)
    status = app.exec_()
    sys.exit(status)
