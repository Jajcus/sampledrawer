
import logging
import os

from PySide2.QtCore import Slot, Signal, QTimer, QObject, QItemSelection, Qt
from PySide2.QtWidgets import QApplication
from PySide2.QtWidgets import QFileSystemModel, QAbstractItemView

logger = logging.getLogger("filebrowser")

class FileBrowser(QObject):
    file_selected = Signal(str)
    def __init__(self, file_tree, program_args):
        QObject.__init__(self)
        self.file_tree = file_tree
        self.model = QFileSystemModel(file_tree)
        if program_args.root:
            self.model.setRootPath(program_args.root)
            self.current_path = program_args.root
        else:
            self.model.setRootPath("")
            self.current_path = os.path.realpath(os.curdir)
        self.file_tree.setModel(self.model)
        self.file_tree.sortByColumn(0, Qt.AscendingOrder)
        self.file_tree.setSortingEnabled(True)
        index = self.model.index(self.current_path)
        if program_args.root:
            self.file_tree.setRootIndex(index)
        self.file_tree.setExpanded(index, True)
        self.file_tree.setCurrentIndex(index)
        self.file_tree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.model.directoryLoaded.connect(self.directory_loaded)
        self.model.dataChanged.connect(self.data_changed)
        selection_model = self.file_tree.selectionModel()
        selection_model.selectionChanged.connect(self.selection_changed)

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
        self.file_tree.scrollTo(index)
        self.file_tree.resizeColumnToContents(0)

    @Slot(QItemSelection)
    def selection_changed(self, selection):
        indexes = selection.indexes()
        if indexes:
            index = indexes[0]
            path = self.model.filePath(index)
            if os.path.isfile(path):
                self.file_selected.emit(path)


