
import logging
import os

from PySide2.QtCore import Slot, Signal, QTimer, QObject, QItemSelection, Qt, QDir
from PySide2.QtWidgets import QApplication
from PySide2.QtWidgets import QAbstractItemView
from PySide2.QtGui import QStandardItemModel, QIcon, QStandardItem

logger = logging.getLogger("librarytree")

class LibraryTree(QObject):
    def __init__(self, app, window):
        QObject.__init__(self)
        self.app = app
        self.library = app.library
        self.lib_tree = window.lib_tree
        self.items = {}
        self.model = QStandardItemModel()
        self.lib_tree.setHeaderHidden(True)
        self.lib_tree.setModel(self.model)
        self.lib_tree.sortByColumn(0, Qt.AscendingOrder)
        self.lib_tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        selection_model = self.lib_tree.selectionModel()
        selection_model.selectionChanged.connect(self.selection_changed)
        self.reload()

    def reload(self):
        self.model.clear()
        self.items = {}
        for tag in sorted(self.library.get_tags()):
            logger.debug("Creating item(s) for tag %r", tag)
            parent_obj = self.model.invisibleRootItem()
            if tag.startswith("/"):
                parents = []
                parent = tag.rsplit("/", 1)[0]
                while parent:
                    logger.debug("Considering parent: %r", parent)
                    parents.insert(0, parent)
                    parent = parent.rsplit("/", 1)[0]
                for parent in parents:
                    item = self.items.get(parent)
                    if not item:
                        logger.debug("Creating item for: %r", parent)
                        item = self.create_item(parent)
                        parent_obj.appendRow(item)
                    parent_obj = item
            item = self.create_item(tag)
            self.items[tag] = item
            parent_obj.appendRow(item)

    def create_item(self, name):
        if name.startswith("/"):
            short_name = name.rsplit("/", 1)[1]
            icon = QIcon.fromTheme("folder")
        else:
            short_name = name
            icon = QIcon.fromTheme("tag")
        item = QStandardItem(icon, short_name)
        item.setToolTip(name)
        return item

    @Slot(QItemSelection)
    def selection_changed(self, selection):
        logger.debug("selection changed")


