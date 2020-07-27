
import logging
import os

from PySide2.QtCore import QFile, Slot, QResource
from PySide2.QtGui import QIcon
from PySide2.QtUiTools import QUiLoader

from .file_browser import FileBrowser
from .lib_tree import LibraryTree
from .lib_items import LibraryItems
from .player import Player
from ..metadata import Metadata
from .file_analyzer import AsyncFileAnalyzer, FileKey
from .metadata_browser import MetadataBrowser
from .waveform import WaveformWidget, WaveformCursorWidget

from . import __path__ as PKG_PATH

logger = logging.getLogger("main_window")

UI_FILENAME = os.path.join(PKG_PATH[0], "main_window.ui")
RESOURCE_FILENAMES = [os.path.join(PKG_PATH[0], "resources.rcc"),
                      "resources.rcc"]

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
        for path in RESOURCE_FILENAMES:
            if os.path.exists(path):
                logger.debug("Loading resources from %r", path)
                QResource.registerResource(path)
        logger.debug("Icon search path: %r", QIcon.themeSearchPaths())
        ui_file = QFile(UI_FILENAME)
        ui_file.open(QFile.ReadOnly)
        loader = UiLoader()
        self.window = loader.load(ui_file)
        self.file_browser = FileBrowser(app, self.window)
        self.lib_tree = LibraryTree(app, self.window)
        self.lib_items = LibraryItems(app, self.window, self.lib_tree)
        self.sample_player = Player(self.window)
        self.file_analyzer = AsyncFileAnalyzer()
        self.metadata_browser = MetadataBrowser(self.window.metadata_view)
        self.file_browser.file_selected.connect(self.sample_player.file_selected)
        self.file_browser.file_selected.connect(self.file_selected)
        self.lib_items.item_selected.connect(self.item_selected)
        self.current_file = None

    def show(self):
        self.window.show()

    @Slot(Metadata)
    def file_selected(self, path):
        path = FileKey(path)
        self.current_file = path
        self.window.waveform.set_waveform(None)
        self.window.waveform.set_duration(0)
        self.window.waveform.set_cursor_position(-1)
        self.file_analyzer.request_waveform(path, self.waveform_received)
        self.file_analyzer.request_file_metadata(path, self.metadata_received)

    @Slot()
    def item_selected(self, metadata):
        logger.debug("library item selected: %r", metadata)
        if metadata:
            path = self.app.library.get_library_object_path(metadata)
            self.window.waveform.set_duration(metadata.duration)
        else:
            path = None
        self.current_file = path
        self.window.waveform.set_waveform(None)
        self.window.waveform.set_cursor_position(-1)
        if path:
            self.file_analyzer.request_waveform(path, self.waveform_received)
        self.metadata_browser.set_metadata(metadata)
        self.sample_player.file_selected(path)

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

