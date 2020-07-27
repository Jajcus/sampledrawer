
import logging

from PySide2.QtWidgets import QApplication

from .signal_handler import SignalHandler
from .main_window import MainWindow

logger = logging.getLogger("gui.app")

class GUIApplication:
    def __init__(self, app):
        self.app = app
        self.args = app.args
        self.library = app.library
        self.analyzer = app.analyzer
        logging.debug("qt_argv: %r", self.args.qt_argv)
        self.qapp = QApplication(self.args.qt_argv)
    def start(self):
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
            self.appp.exit(code)
