
import logging
import os

from PySide2.QtCore import Slot, Signal, QTimer, QObject, QItemSelection, Qt, QDir
from PySide2.QtWidgets import QApplication
from PySide2.QtWidgets import QFileSystemModel, QAbstractItemView

logger = logging.getLogger("file_browser")

NAME_FILTERS = [
        ("Sound Files", ["*.wav", "*.ogg", "*.oga", "*.mp3"]),
        ("All Files", ["*"]),
        ]

class FileBrowser(QObject):
    file_selected = Signal(str)
    def __init__(self, app, window):
        QObject.__init__(self)
        self.app = app
        self.view = window.file_tree
        self.show_hidden_chk = window.show_hidden
        self.name_filter_combo = window.name_filter
        self.model = QFileSystemModel(self.view)
        if app.args.root:
            self.model.setRootPath(app.args.root)
            self.current_path = app.args.root
        else:
            self.model.setRootPath("")
            self.current_path = os.path.realpath(os.curdir)
        self.view.setModel(self.model)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.setSortingEnabled(True)
        index = self.model.index(self.current_path)
        if app.args.root:
            self.view.setRootIndex(index)
        self.view.setExpanded(index, True)
        self.view.setCurrentIndex(index)
        self.view.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.add_name_filters()
        self.apply_show_hidden()
        self.apply_name_filters()
        self.model.setNameFilterDisables(False)
        self.model.directoryLoaded.connect(self.directory_loaded)
        self.model.dataChanged.connect(self.data_changed)
        selection_model = self.view.selectionModel()
        selection_model.selectionChanged.connect(self.selection_changed)
        self.show_hidden_chk.stateChanged.connect(self.apply_show_hidden)
        self.name_filter_combo.currentIndexChanged.connect(self.apply_name_filters)

    def add_name_filters(self):
        for name, filters in NAME_FILTERS:
            label = "{} ({})".format(name, ", ".join(filters))
            self.name_filter_combo.addItem(label, filters)
        self.name_filter_combo.setCurrentIndex(0)

    @Slot()
    def apply_show_hidden(self):
        show = self.show_hidden_chk.checkState()
        logging.debug("apply_show_hidden(): %r", show)
        flags = QDir.AllDirs | QDir.Files | QDir.NoDotAndDotDot
        if show:
            flags |= QDir.Hidden
        self.model.setFilter(flags)
        QTimer.singleShot(100, self.scroll_to_current)

    @Slot()
    def apply_name_filters(self):
        filters = self.name_filter_combo.currentData()
        self.model.setNameFilters(filters)
        QTimer.singleShot(100, self.scroll_to_current)

    @Slot(str)
    def directory_loaded(self, path):
        logger.debug("directory loaded: %s", path)
        if path == self.current_path:
            logger.debug("requesting scrolling")
            QTimer.singleShot(100, self.scroll_to_current)

    @Slot()
    def data_changed(self, *args):
        logger.debug("Data changed: %r", args)

    @Slot()
    def scroll_to_current(self):
        index = self.model.index(self.current_path)
        self.view.scrollTo(index)
        self.view.resizeColumnToContents(0)

    @Slot(QItemSelection)
    def selection_changed(self, selection):
        indexes = selection.indexes()
        if indexes:
            index = indexes[0]
            path = self.model.filePath(index)
            if os.path.isfile(path):
                self.file_selected.emit(path)
            self.current_path = path


