
import logging
import os

from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QFile

from .filebrowser import FileBrowser
from .librarytree import LibraryTree
from .sampleplayer import SamplePlayer
from .sampleanalyzer import AsyncSampleAnalyzer, FileKey
from .metadatabrowser import MetadataBrowser
from .waveform import WaveformWidget, WaveformCursorWidget

from . import __path__ as PKG_PATH

logger = logging.getLogger("mainwindow")

UI_FILENAME = os.path.join(PKG_PATH[0], "mainwindow.ui")

class UiLoader(QUiLoader):
    def createWidget(self, className, parent=None, name=""):
        if className == "WaveformWidget":
            widget = WaveformWidget(parent)
            widget.setObjectName(name)
            return widget
        return super(UiLoader, self).createWidget(className, parent, name)

class MainWindow:
    def __init__(self, app):
        self.app = app
        ui_file = QFile(UI_FILENAME)
        ui_file.open(QFile.ReadOnly)
        loader = UiLoader()
        self.window = loader.load(ui_file)
        self.file_browser = FileBrowser(app, self.window)
        self.lib_tree = LibraryTree(app, self.window)
        self.sample_player = SamplePlayer(self.window)
        self.sample_analyzer = AsyncSampleAnalyzer()
        self.metadata_browser = MetadataBrowser(self.window.metadata_view)
        self.file_browser.file_selected.connect(self.sample_player.file_selected)
        self.file_browser.file_selected.connect(self.file_selected)
        self.current_file = None

    def show(self):
        self.window.show()

    def file_selected(self, path):
        path = FileKey(path)
        self.current_file = path
        self.window.waveform.set_waveform(None)
        self.window.waveform.set_duration(0)
        self.window.waveform.set_cursor_position(-1)
        self.sample_analyzer.request_waveform(path, self.waveform_received)
        self.sample_analyzer.request_file_metadata(path, self.metadata_received)

    def waveform_received(self, path, waveform):
        if path == self.current_file:
            self.window.waveform.set_waveform(waveform)

    def metadata_received(self, path, metadata):
        if path != self.current_file:
            logger.debug("Received data for %r while wating for %r",
                         path, self.current_file)
            pass
        logger.debug("Got %r metadata: %r", path, metadata)
        self.metadata_browser.set_metadata(metadata)
        self.window.waveform.set_duration(metadata.duration)

