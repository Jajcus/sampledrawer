
import logging
import os

from PySide2.QtCore import Slot, Signal, QTimer, QObject, QItemSelection, Qt
from PySide2.QtWidgets import QAbstractItemView
from PySide2.QtGui import QStandardItemModel, QIcon, QStandardItem

from ..search import SearchQuery

logger = logging.getLogger("librarytree")

ITEM_LIMIT = 100

class LibraryItems(QObject):
    def __init__(self, app, window, lib_tree):
        QObject.__init__(self)
        self.app = app
        self.lib_tree = lib_tree
        self.library = app.library
        self.view = window.lib_items
        self.tree_conditions = []
        self.items = []
        self.items_incomplete = False
        self.model = QStandardItemModel()
        self.model.setColumnCount(1)
        self.view.setHeaderHidden(True)
        self.view.setIndentation(0)
        self.view.setModel(self.model)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        tree_selection_model = window.lib_tree.selectionModel()
        tree_selection_model.selectionChanged.connect(self.tree_selection_changed)

    def reload(self):
        self.model.clear()
        icon = QIcon.fromTheme("audio-x-generic")
        for item in self.items:
            s_item = QStandardItem(icon, item.name)
            s_item.setData(item)
            self.model.appendRow([s_item])
        if self.items_incomplete:
            s_item = QStandardItem("…and more")
            self.model.appendRow([s_item])

    @Slot(QItemSelection)
    def tree_selection_changed(self, selection):
        logger.debug("tree selection changed")
        self.tree_conditions = self.lib_tree.get_current_conditions()
        self.run_query()

    def run_query(self):
        query = SearchQuery(self.tree_conditions)
        items = self.library.get_items(query, limit=ITEM_LIMIT + 1)
        if len(items) > ITEM_LIMIT:
            self.items_incomplete = True
            self.items = items[:ITEM_LIMIT]
        else:
            self.items_incomplete = False
            self.items = items
        self.reload()
