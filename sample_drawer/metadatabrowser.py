
import logging
import os

from PySide2.QtCore import Slot, Signal, Qt, QObject
from PySide2.QtCore import QAbstractItemModel, QModelIndex
from PySide2.QtGui import QStandardItemModel, QStandardItem

logger = logging.getLogger("metadatabrowser")

class MetadataBrowser(QObject):
    def __init__(self, metadata_view):
        QObject.__init__(self)
        self.view = metadata_view
        self.metadata = None
        self.model = QStandardItemModel(1, 2)
        self.model.setHorizontalHeaderItem(0, QStandardItem("Key"))
        self.model.setHorizontalHeaderItem(1, QStandardItem("Value"))
        self.view.setModel(self.model)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.setSortingEnabled(False)

    @Slot()
    def set_metadata(self, metadata):
        self.metadata = metadata
        if metadata:
            self.model.setRowCount(len(self.metadata))
            for i, key in enumerate(sorted(metadata)):
                self.model.setItem(i, 0, QStandardItem(key));
                self.model.setItem(i, 1, QStandardItem(str(metadata[key])));
        else:
            self.model.setRowCount(0)
