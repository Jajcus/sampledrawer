
import logging
import json
import socket

from urllib.parse import urlunsplit

from PySide2.QtCore import Slot, Signal, QObject, QItemSelection, Qt, QMimeData, QByteArray, \
                           QModelIndex
from PySide2.QtWidgets import QAbstractItemView, QCompleter
from PySide2.QtGui import QStandardItemModel, QIcon, QStandardItem

from ..search import SearchQuery, CompletionQuery

logger = logging.getLogger("lib_items")

ITEM_LIMIT = 100
COMPLETION_LIMIT = 10

MIMETYPES = {
        "WAV": "audio/x-wav",
        "OGG": "audio/ogg",
        "FLAC": "audio/x-flac",
        "AIFF": "audio/x-aiff",
        }


class ItemMimeData(QMimeData):
    def __init__(self, app, items):
        QMimeData.__init__(self)
        self._app = app
        self._items = [item.data() for item in items]
        self._paths = None
        self._formats = None

    def get_items(self):
        return self._items

    def formats(self):
        if self._formats is not None:
            return self._formats
        result = ["application/x-sampledrawer-lib-items"]
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

        if mime_type == "application/x-sampledrawer-lib-items":
            result = []
            for item in self._items:
                result.append({"name": item.name, "md5": item.md5, "path": item.path})
            return json.dumps(result)

        paths = self._paths
        if paths is None:
            paths = []
            for item in self._items:
                path = self._app.library.get_pretty_path(item, timeout=60)
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
    def __init__(self, app):
        QStandardItemModel.__init__(self)
        self._app = app

    def mimeData(self, indexes):
        logger.debug("mimeData(%r)", indexes)
        items = [self.itemFromIndex(index) for index in indexes]
        return ItemMimeData(self._app, items)

    def supportedDragActions(self):
        return Qt.CopyAction

    def supportedDropActions(self):
        return Qt.CopyAction

    def canDropMimeData(self, data, action, row, column, parent):
        logger.debug("canDropMimeData%r", (data, action, row, column, parent))
        if action != Qt.CopyAction:
            logger.debug("Not a copy - rejecting")
            return False
        if isinstance(data, ItemMimeData):
            logger.debug("local library item drop, rejecting")
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
            paths = []
            for url in data.urls():
                if not url.isLocalFile():
                    logger.warning("Ignoring %r not a file", url.toString())
                    continue
                if (url.host() and url.host() != "localhost"
                        and url.host() != socket.gethostname()):
                    logger.warning("Ignoring %r not a local file", url.toString())
                    continue
                path = url.path()
                paths.append(path)
            self._app.main_window.import_files(paths)
            return True
        return False


class LibraryItems(QObject):
    item_selected = Signal(object)
    item_activated = Signal(object)

    def __init__(self, app, window, lib_tree):
        QObject.__init__(self)
        self.app = app
        self.lib_tree = lib_tree
        self.library = app.library
        self.input = window.search_query_input
        self.view = window.lib_items
        self.tree_conditions = []
        self.items = []
        self.items_incomplete = False
        self.model = ItemModel(self.app)
        self.model.setColumnCount(1)
        self.compl_model = QStandardItemModel()
        self.compl_model.setColumnCount(1)
        self.completer = QCompleter(self.compl_model)
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setModelSorting(QCompleter.CaseSensitivelySortedModel)
        self.input.setCompleter(self.completer)
        self.view.setHeaderHidden(True)
        self.view.setIndentation(0)
        self.view.setModel(self.model)
        self.view.sortByColumn(0, Qt.AscendingOrder)
        self.view.setDragEnabled(True)
        self.view.setAcceptDrops(True)
        self.view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        selection_model = self.view.selectionModel()
        selection_model.selectionChanged.connect(self.selection_changed)
        tree_selection_model = window.lib_tree.selectionModel()
        tree_selection_model.selectionChanged.connect(self.tree_selection_changed)
        self.input.editingFinished.connect(self.query_entered)
        self.input.textChanged.connect(self.query_changed)
        self.view.doubleClicked.connect(self.double_clicked)
        self.run_query()

    def reload(self):
        self.model.clear()
        self.item_selected.emit(None)
        icon = QIcon.fromTheme("audio-x-generic")
        for item in self.items:
            s_item = QStandardItem(icon, item.name)
            s_item.setDragEnabled(True)
            s_item.setDropEnabled(False)
            s_item.setData(item)
            self.model.appendRow([s_item])
        if self.items_incomplete:
            s_item = QStandardItem("…and more")
            s_item.setDragEnabled(False)
            s_item.setDropEnabled(False)
            self.model.appendRow([s_item])

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

    @Slot(QModelIndex)
    def double_clicked(self, index):
        s_item = self.model.itemFromIndex(index)
        metadata = s_item.data()
        self.item_activated.emit(metadata)

    @Slot(QItemSelection)
    def tree_selection_changed(self, selection):
        logger.debug("tree selection changed")
        self.tree_conditions = self.lib_tree.get_current_conditions()
        self.run_query()

    def run_query(self):
        text_query = self.input.text()
        query = SearchQuery.from_string(text_query)
        query.add_conditions(self.tree_conditions)
        items = self.library.get_items(query, limit=ITEM_LIMIT + 1)
        if len(items) > ITEM_LIMIT:
            self.items_incomplete = True
            self.items = items[:ITEM_LIMIT]
        else:
            self.items_incomplete = False
            self.items = items
        self.reload()

    @Slot()
    def query_entered(self):
        self.run_query()

    @Slot()
    def query_changed(self, text):
        compl_query = CompletionQuery.from_string(text)
        if compl_query:
            columns = ["offsets(compl_fts.fts)", "compl_fts.content"]
            compl_query.add_conditions(self.tree_conditions)
            sql_query, params = compl_query.as_sql(columns=columns)
            logger.debug("completing %r with query %r %r",
                         compl_query.prefix, sql_query, params)
            matches = self.library.get_completions(compl_query,
                                                   limit=COMPLETION_LIMIT)
            self.compl_model.clear()
            for match in sorted(matches):
                match = text[:compl_query.start_index] + match
                logger.debug("Adding match: %r", match)
                s_item = QStandardItem(match)
                self.compl_model.appendRow([s_item])
        else:
            self.model.clear()
