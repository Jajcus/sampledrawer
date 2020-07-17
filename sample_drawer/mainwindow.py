
import logging
import os

from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QFile

from .filebrowser import FileBrowser
from .sampleplayer import SamplePlayer
from .sampleanalyzer import SampleAnalyzer, FileKey
from .metadatabrowser import MetadataBrowser

from . import __path__ as PKG_PATH

logger = logging.getLogger("mainwindow")

UI_FILENAME = os.path.join(PKG_PATH[0], "mainwindow.ui")

class MainWindow:
    def __init__(self, program_args):
        ui_file = QFile(UI_FILENAME)
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        self.window = loader.load(ui_file)
        self.file_browser = FileBrowser(self.window, program_args)
        self.sample_player = SamplePlayer(self.window)
        self.sample_analyzer = SampleAnalyzer()
        self.metadata_browser = MetadataBrowser(self.window.metadata_view)
        self.file_browser.file_selected.connect(self.sample_player.file_selected)
        self.file_browser.file_selected.connect(self.file_selected)
        self.current_file = None
    def show(self):
        self.window.show()
    def file_selected(self, path):
        path = FileKey(path)
        self.current_file = path
        self.sample_analyzer.request_file_metadata(path, self.metadata_received)

    def metadata_received(self, path, metadata):
        if path != self.current_file:
            logger.debug("Received data for %r while wating for %r",
                         path, self.current_file)
            pass
        logger.debug("Got %r metadata: %r", path, metadata)
        self.metadata_browser.set_metadata(metadata)

