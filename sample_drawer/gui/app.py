
import logging
import os

from PySide2.QtCore import QResource
from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QApplication

from .signal_handler import SignalHandler
from .main_window import MainWindow
from .log_window import LogWindow
from ..audiodrivers import get_audio_driver, AudioDriverError

from . import __path__ as PKG_PATH

RESOURCE_FILENAMES = [os.path.join(PKG_PATH[0], "resources.rcc"),
                      "resources.rcc"]

logger = logging.getLogger("gui.app")


class GUIApplication:
    def __init__(self, app):
        self.started = False
        self.app = app
        self.args = app.args
        self.config = app.config
        self.library = app.library
        self.workplace = app.workplace
        self.analyzer = app.analyzer
        logging.debug("qt_argv: %r", self.args.qt_argv)
        self.qapp = QApplication(self.args.qt_argv)
        self.qapp.setApplicationName("Sample Drawer")
        for path in RESOURCE_FILENAMES:
            if os.path.exists(path):
                logger.debug("Loading resources from %r", path)
                QResource.registerResource(path)
        QIcon.setThemeSearchPaths(QIcon.themeSearchPaths()
                                  + ["/home/jajcus/git/sampledrawer/icons"])
        logger.debug("Icon search path: %r", QIcon.themeSearchPaths())
        QIcon.setFallbackSearchPaths([":icons/"] + QIcon.fallbackSearchPaths())
        logger.debug("Icon fallback path: %r", QIcon.fallbackSearchPaths())
        logger.debug("Theme name %r", QIcon.themeName())
        logger.debug("Fallback theme name: %r", QIcon.fallbackThemeName())
        self.qapp.setWindowIcon(QIcon(":icons/sampledrawer.svg"))

    def start(self):
        try:
            self.audio_driver = get_audio_driver(self.args)
        except AudioDriverError as err:
            logger.error("Audio driver initialization error: %s", err)
            return 1
        self.log_window = LogWindow(self)
        self.main_window = MainWindow(self)
        self.main_window.show()
        signal_handler = SignalHandler()
        signal_handler.activate()
        self.qapp.aboutToQuit.connect(signal_handler.deactivate)
        self.started = True
        try:
            return self.qapp.exec_()
        finally:
            self.started = False

    def exit(self, code):
        if self.qapp and self.started:
            self.qapp.exit(code)
        else:
            self.app.exit(code)
