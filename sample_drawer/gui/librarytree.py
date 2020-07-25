
import logging
import os

from PySide2.QtCore import Slot, Signal, QTimer, QObject, QItemSelection, Qt
from PySide2.QtWidgets import QApplication
from PySide2.QtWidgets import QAbstractItemView
from PySide2.QtGui import QStandardItemModel, QIcon, QStandardItem

from ..search import TagQuery

logger = logging.getLogger("librarytree")

class LibraryTree(QObject):
    def __init__(self, app, window):
        QObject.__init__(self)
        self.app = app
        self.library = app.library
        self.lib_tree = window.lib_tree
        self.items = {}
        self.model = QStandardItemModel()
        self.model.setColumnCount(2)
        self.lib_tree.setHeaderHidden(True)
        self.lib_tree.setModel(self.model)
        self.lib_tree.sortByColumn(0, Qt.AscendingOrder)
        self.lib_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.lib_tree.expanded.connect(self.resize_columns)
        self.lib_tree.collapsed.connect(self.resize_columns)
        selection_model = self.lib_tree.selectionModel()
        selection_model.selectionChanged.connect(self.selection_changed)
        self.reload()

    def reload(self):
        self.model.clear()
        self.items = {}
        for tag, count in sorted(self.library.get_tags()):
            logger.debug("Creating item(s) for tag %r", tag)
            parent_obj = self.model.invisibleRootItem()
            if tag.startswith("/") and tag != "/":
                parent = tag.rsplit("/", 1)[0]
                if not parent:
                    parent = "/"
                item, c_item = self.items[parent]
                parent_obj = item
            item, c_item = self.create_items(tag, count)
            self.items[tag] = (item, c_item)
            parent_obj.appendRow([item, c_item])
        self.resize_columns()

    def create_items(self, name, count):
        if name.startswith("/"):
            if name == "/":
                short_name = "all"
            else:
                short_name = name.rsplit("/", 1)[1]
            icon = QIcon.fromTheme("folder")
        else:
            short_name = name
            icon = QIcon.fromTheme("tag")
        item = QStandardItem(icon, short_name)
        item.setToolTip(name)
        item.setData(name)
        c_item = QStandardItem(str(count))
        c_item.setTextAlignment(Qt.AlignRight)
        return item, c_item

    def get_current_conditions(self):
        result = []
        for index in self.lib_tree.selectedIndexes():
            if index.column() > 0:
                continue
            item = self.model.itemFromIndex(index)
            logger.debug("Selected item: %r", item)
            tag = item.data()
            result.append(TagQuery(tag))
        return result

    @Slot()
    def resize_columns(self, index=None):
        self.lib_tree.resizeColumnToContents(0)
        self.lib_tree.resizeColumnToContents(1)

    @Slot(QItemSelection)
    def selection_changed(self, selection):
        logger.debug("selection changed")


