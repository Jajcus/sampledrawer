
import logging
import os

from PySide2.QtCore import QFile, QObject, QEvent, Signal
from PySide2.QtGui import QPalette
from PySide2.QtUiTools import QUiLoader

from .file_browser import FileBrowser
from .lib_tree import LibraryTree
from .lib_items import LibraryItems
from .player import Player
from ..metadata import Metadata
from .file_analyzer import AsyncFileAnalyzer, FileKey
from .metadata_browser import MetadataBrowser
from .waveform import WaveformWidget
from .workplace import WorkplaceItems
from .import_dialog import ImportDialog

from . import __path__ as PKG_PATH

logger = logging.getLogger("main_window")

UI_FILENAME = os.path.join(PKG_PATH[0], "main_window.ui")

STYLESHEET = """
QTreeView:!active {{
    selection-background-color: {inactive_hl_color};
    }}
"""


def color_to_qss(color):
    return "rgb({}, {}, {}, {})".format(color.red(),
                                        color.green(),
                                        color.blue(),
                                        color.alpha())


class UiLoader(QUiLoader):
    def createWidget(self, className, parent=None, name=""):
        if className == "WaveformWidget":
            widget = WaveformWidget(parent)
            widget.setObjectName(name)
            return widget
        return super(UiLoader, self).createWidget(className, parent, name)


class CloseEventFilter(QObject):
    closing = Signal()

    def __init__(self, parent):
        QObject.__init__(self, parent)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Close:
            self.closing.emit()
        return False


class MainWindow:
    def __init__(self, app):
        self.app = app
        ui_file = QFile(UI_FILENAME)
        ui_file.open(QFile.ReadOnly)
        loader = UiLoader()
        self.window = loader.load(ui_file)
        event_filter = CloseEventFilter(self.window)
        self.window.installEventFilter(event_filter)
        event_filter.closing.connect(self.app.log_window.close)
        self.set_stylesheet()
        self.file_browser = FileBrowser(app, self.window)
        self.lib_tree = LibraryTree(app, self.window)
        self.lib_items = LibraryItems(app, self.window, self.lib_tree)
        self.sample_player = Player(app, self.window)
        self.file_analyzer = AsyncFileAnalyzer()
        self.workplace_items = WorkplaceItems(app, self.window, self.file_analyzer)
        self.metadata_browser = MetadataBrowser(self.window.metadata_view)
        self.file_browser.file_selected.connect(self.sample_player.file_selected)
        self.file_browser.file_selected.connect(self.file_selected)
        self.file_browser.file_activated.connect(self.file_activated)
        self.lib_items.item_selected.connect(self.item_selected)
        self.lib_items.item_activated.connect(self.item_activated)
        self.workplace_items.item_selected.connect(self.wp_item_selected)
        self.workplace_items.item_activated.connect(self.wp_item_activated)
        log_window = self.app.log_window.window
        self.window.action_log_window.toggled.connect(log_window.setVisible)
        self.current_file = None

    def set_stylesheet(self):
        palette = self.window.palette()
        hl_color = palette.color(QPalette.Active, QPalette.Highlight)
        hl_text_color = palette.color(QPalette.Active, QPalette.HighlightedText)

        if hl_color.lightnessF() < hl_text_color.lightnessF():
            inactive_hl_color = hl_color.lighter()
        else:
            inactive_hl_color = hl_color.darker()

        hue, sat, lig, alpha = inactive_hl_color.getHslF()
        inactive_hl_color.setHslF(hue, sat / 2, lig, alpha)

        params = {
                "active_hl_color":  color_to_qss(hl_color),
                "inactive_hl_color":  color_to_qss(inactive_hl_color),
                }
        stylesheet = STYLESHEET.format(**params)
        logger.debug("custom style: %r", stylesheet)
        self.window.setStyleSheet(stylesheet)

    def show(self):
        self.window.show()

    def file_selected(self, path):
        if not path:
            self.current_file = None
            return
        path = FileKey(path)
        self.current_file = path
        self.window.waveform.set_waveform(None)
        self.window.waveform.set_duration(0)
        self.window.waveform.set_cursor_position(-1)
        self.file_analyzer.request_waveform(path, self.waveform_received)
        self.file_analyzer.request_file_metadata(path, self.metadata_received)

    def file_activated(self, path):
        path = FileKey(path)
        if path != self.current_file:
            self.file_selected(path)
        self.sample_player.play_pause_clicked()

    def item_selected(self, metadata):
        logger.debug("library item selected: %r", metadata)
        if metadata:
            path = self.app.library.get_item_path(metadata)
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

    def item_activated(self, metadata):
        path = self.app.library.get_item_path(metadata)
        if path != self.current_file:
            self.item_selected(metadata)
        self.sample_player.play_pause_clicked()

    def wp_item_selected(self, item):
        if isinstance(item, Metadata):
            metadata = item
        else:
            metadata = None
        logger.debug("workplace item selected: %r", metadata)
        if metadata:
            path = self.app.workplace.get_item_path(metadata)
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

    def wp_item_activated(self, item):
        if not isinstance(item, Metadata):
            return
        metadata = item
        path = self.app.workplace.get_item_path(metadata)
        if path != self.current_file:
            self.wp_item_selected(item)
        self.sample_player.play_pause_clicked()

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
        if metadata:
            self.window.waveform.set_duration(metadata.duration)

    def import_files(self, paths):
        dialog = ImportDialog(self)
        if len(paths) == 1 and os.path.isdir(paths[0]):
            root = os.path.dirname(paths[0])
        else:
            root = os.path.commonprefix(paths).rsplit(os.sep, 1)[0]
        file_paths = []
        for path in paths:
            if os.path.isdir(path):
                for dirpath, dirnames, filenames in os.walk(path):
                    for filename in filenames:
                        file_paths.append(os.path.join(dirpath, filename))
            elif os.path.isfile(path):
                file_paths.append(path)
            else:
                logger.warning("Cannot import %r: is not a regular file", path)
        if file_paths:
            dialog.load_files(file_paths, root)
            self.lib_tree.reload()
        else:
            logger.warning("Nothing to import")
