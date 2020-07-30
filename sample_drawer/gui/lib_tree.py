
import logging
import os

from PySide2.QtCore import Slot, Signal, QTimer, QObject, QItemSelection, Qt, QItemSelectionModel
from PySide2.QtWidgets import QApplication
from PySide2.QtWidgets import QAbstractItemView
from PySide2.QtGui import QStandardItemModel, QIcon, QStandardItem

from ..search import TagIncludeQuery

logger = logging.getLogger("lib_tree")

class LibraryTree(QObject):
    def __init__(self, app, window):
        QObject.__init__(self)
        self.app = app
        self.library = app.library
        self.view = window.lib_tree
        self.items = {}
        self.model = QStandardItemModel()
        self.model.setColumnCount(2)
        self.view.setHeaderHidden(True)
        self.view.setModel(self.model)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.expanded.connect(self.resize_columns)
        self.view.collapsed.connect(self.resize_columns)
        self.reload()
        selection_model = self.view.selectionModel()
        selection_model.select(self.items["/"][0].index(),
                               QItemSelectionModel.Select)
        selection_model.selectionChanged.connect(self.selection_changed)

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
        for index in self.view.selectedIndexes():
            if index.column() > 0:
                continue
            item = self.model.itemFromIndex(index)
            logger.debug("Selected item: %r", item)
            tag = item.data()
            result.append(TagIncludeQuery(tag))
        return result

    @Slot()
    def resize_columns(self, index=None):
        self.view.resizeColumnToContents(0)
        self.view.resizeColumnToContents(1)

    @Slot(QItemSelection)
    def selection_changed(self, selection):
        logger.debug("selection changed")


