
import logging
import os

from functools import partial
from urllib.parse import urlunsplit

from PySide2.QtCore import Slot, Signal, QTimer, QObject, QItemSelection, Qt, QMimeData, QByteArray
from PySide2.QtWidgets import QAbstractItemView, QCompleter, QShortcut
from PySide2.QtGui import QStandardItemModel, QIcon, QStandardItem, QKeySequence

from ..search import SearchQuery, CompletionQuery
from .lib_items import MIMETYPES

logger = logging.getLogger("gui.scratchpad")

class ScratchpadItemMimeData(QMimeData):
    def __init__(self, app, items):
        QMimeData.__init__(self)
        self._app = app
        self._items = [item.data() for item in items]
        self._paths = None
        self._formats = None
    def formats(self):
        if self._formats is not None:
            return self._formats
        result = []
        if len(self._items) == 1:
            metadata = self._items[0]
            mime_type = MIMETYPES.get(metadata.format, "application/octet-stream")
            result.append(mime_type)
        result.append("text/uri-list")
        result.append("text/plain")
        self._formats = result
        return result
    def hasFormat(self, fmt):
        return fmt in self.formats()
    def retrieveData(self, mime_type, var_type):
        logger.debug("retrieveData(%r, %r)", mime_type, var_type)
        if mime_type not in self.formats():
            logger.debug("unsupported type requested")
            return None

        paths = self._paths
        if paths is None:
            paths = []
            for item in self._items:
                path = self._app.scratchpad.get_object_path(item)
                paths.append(path)
            self._paths = paths

        if mime_type == "text/plain":
            return " ".join(paths)
        elif mime_type == "text/uri-list":
            uris = []
            for path in paths:
                uri = urlunsplit(("file", "localhost", path, None, None))
                uris.append(uri.encode("utf-8"))
            # text/uri-list is defined to use CR LF line endings
            return QByteArray.fromRawData(b"\r\n".join(uris) + b"\r\n")
        else:
            path = paths[0]
            with open(path, "rb") as data_f:
                data = data_f.read()
            return QByteArray.fromRawData(data)

class ItemModel(QStandardItemModel):
    def __init__(self, scratchpad_items):
        QStandardItemModel.__init__(self)
        self._scratchpad_items = scratchpad_items
        self._app = scratchpad_items.app
    def mimeData(self, indexes):
        logger.debug("mimeData(%r)", indexes)
        items = [ self.itemFromIndex(index) for index in indexes ]
        return ScratchpadItemMimeData(self._app, items)
    def supportedDragActions(self):
        return Qt.CopyAction
    def supportedDropActions(self):
        return Qt.CopyAction
    def canDropMimeData(self, data, action, row, column, parent):
        logger.debug("canDropMimeData%r", (data, action, row, column, parent))
        if action != Qt.CopyAction:
            logger.debug("Not a copy - rejecting")
            return False
        logger.debug("offered formats: %r", data.formats())
        if "text/uri-list" in data.formats():
            return True
        return False
    def dropMimeData(self, data, action, row, column, parent):
        if action != Qt.CopyAction:
            logger.debug("Not a copy - rejecting")
            return False
        logger.debug("offered formats: %r", data.formats())
        if "text/uri-list" in data.formats():
            self._scratchpad_items.import_urls(data.urls())
            return True
        return False


class ScratchpadFolder:
    def __init__(self, path, expanded=False):
        self.path = path
        self.expanded = expanded

class ScratchpadItems(QObject):
    item_selected = Signal(object)
    def __init__(self, app, window, file_analyzer):
        QObject.__init__(self)
        self.app = app
        self.library = app.library
        self.scratchpad = app.scratchpad
        self.file_analyzer = file_analyzer
        self.view = window.scratchpad_items
        self.items = []
        self.folders = {}
        self.model = ItemModel(self)
        self.model.setColumnCount(1)
        self.view.setHeaderHidden(False)
        self.view.setModel(self.model)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.setDragEnabled(True)
        self.view.setAcceptDrops(True)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.selection_model = self.view.selectionModel()
        self.selection_model.selectionChanged.connect(self.selection_changed)
        self.view.expanded.connect(self.folder_expanded)
        self.view.collapsed.connect(self.folder_collapsed)
        self.get_items()
        shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self.view)
        shortcut.activated.connect(self.delete_selected)

    def reload(self):
        expanded = {key for key, s_item
                    in self.folders.items()
                    if s_item.data().expanded}
        self.model.clear()
        self.item_selected.emit(None)
        icon = QIcon.fromTheme("audio-x-generic")
        folder_icon = QIcon.fromTheme("folder")
        folders = {}
        self.folders = folders
        for item in sorted(self.items, key=lambda x: x.path):
            parent_paths = []
            path = item.path
            while "/" in path:
                parent_folder = path.rsplit("/", 1)[0]
                logger.debug("%r is in a folder: %r", path, parent_folder)
                parent = folders.get(parent_folder)
                if parent:
                    logger.debug("%r already here: %r", parent_folder, parent)
                    break
                else:
                    parent_paths.append(parent_folder)
                path = parent_folder
            else:
                logger.debug("starting at root")
                parent = self.model.invisibleRootItem()
            for folder in reversed(parent_paths):
                logger.debug("creating %r", folder)
                name = folder.rsplit("/", 1)[-1]
                s_item = QStandardItem(folder_icon, name)
                folder_o = ScratchpadFolder(folder)
                s_item.setData(folder_o)
                parent.appendRow([s_item])
                parent = s_item
                folders[folder] = s_item
            s_item = QStandardItem(icon, item.name)
            s_item.setDragEnabled(True)
            s_item.setDropEnabled(False)
            s_item.setData(item)
            parent.appendRow([s_item])
        for path in expanded:
            s_item = folders.get(path)
            if not s_item:
                continue
            self.view.expand(s_item.index())

    @Slot()
    def folder_expanded(self, index):
        s_item = self.model.itemFromIndex(index)
        folder = s_item.data()
        if not isinstance(folder, ScratchpadFolder):
            logger.debug("expanded item is not a folder")
            return
        folder.expanded = True

    @Slot()
    def folder_collapsed(self, index):
        s_item = self.model.itemFromIndex(index)
        folder = s_item.data()
        if not isinstance(folder, ScratchpadFolder):
            logger.debug("collapsed item is not a folder")
            return
        folder.expanded = False

    @Slot(QItemSelection)
    def selection_changed(self, selection):
        logger.debug("selection changed")
        indexes = selection.indexes()
        if indexes:
            index = selection.indexes()[0]
            s_item = self.model.itemFromIndex(index)
            metadata = s_item.data()
        else:
            metadata = None
        self.item_selected.emit(metadata)

    def get_items(self):
        self.items = self.scratchpad.get_items()
        self.reload()

    @Slot()
    def delete_selected(self):
        logger.debug("delete_selected()")
        indexes = self.selection_model.selectedIndexes()
        if not indexes:
            logger.warning("Nothing to delete")
            return
        to_delete = []
        for index in indexes:
            item = self.model.itemFromIndex(index)
            deleted = self.scratchpad.delete_item(item.data())
        self.get_items()

    def import_urls(self, urls):
        for url in urls:
            if not url.isLocalFile():
                logger.warning("Ignoring %r not a file", url.toString())
                continue
            if (url.host() and url.host() != "localhost"
                    and url.host() != socket.gethostname()):
                logger.warning("Ignoring %r not a local file", url.toString())
                continue
            path = url.path()
            if os.path.isdir(path):
                self._import_dir(path)
                continue
            elif not os.path.isfile(path):
                logger.warning("Ignoring %r not a regular file", url.toString())
                continue
            self.file_analyzer.request_file_metadata(path,
                                                     self._import_file)
    def _import_file(self, file_key, metadata, folder=""):
        logger.debug("Got metadata for import: %r", metadata)
        self.scratchpad.import_file(metadata, folder=folder)
        self.get_items()
    def _import_dir(self, path):
        logger.debug("Importing dir: %r", path)
        parent_path = os.path.dirname(path)
        for dirpath, dirnames, filenames in os.walk(path):
            folder = os.path.relpath(dirpath, parent_path)
            logger.debug("Target folder: %r", folder)
            for filename in filenames:
                full_path = os.path.join(dirpath, filename)
                importer = partial(self._import_file, folder=folder)
                self.file_analyzer.request_file_metadata(full_path, importer)
