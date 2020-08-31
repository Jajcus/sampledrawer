
import os
import logging
import weakref

from PySide2.QtCore import QFile, QSortFilterProxyModel, Qt
from PySide2.QtUiTools import QUiLoader
from PySide2.QtWidgets import QAbstractItemView
from PySide2.QtGui import QStandardItemModel, QStandardItem, QIcon

from . import __path__ as PKG_PATH

logger = logging.getLogger("log_window")

UI_FILENAME = os.path.join(PKG_PATH[0], "log_window.ui")

LEVELS = [
        ("Critical", logging.CRITICAL, "dialog-error"),
        ("Error", logging.ERROR, "dialog-error"),
        ("Warning", logging.WARNING, "dialog-warning"),
        ("Info", logging.INFO, "dialog-information"),
        ("Debug", logging.DEBUG, None),
        ]

ROLE_LEVEL = Qt.UserRole + 1
MSG_COLUMN = 0


class LogHandler(logging.Handler):
    def __init__(self, window):
        self._window = weakref.ref(window)
        logging.Handler.__init__(self)

    def emit(self, record):
        if record.name == logger.name:
            # ignore logs from this module
            # to prevent infinite recursion
            return
        window = self._window()
        if not window:
            return
        try:
            msg = self.format(record)
            window.add_entry(msg,
                             level=record.levelno,
                             timestamp=record.created)
        except RecursionError:
            raise
        except Exception:
            self.handleError(record)


class LogFilterProxyModel(QSortFilterProxyModel):
    def __init__(self, parent, level):
        self._level = level
        QSortFilterProxyModel.__init__(self, parent)

    def filterAcceptsRow(self, row, parent):
        model = self.sourceModel()
        index = model.index(row, MSG_COLUMN, parent)
        item = model.itemFromIndex(index)
        if item:
            item_level = item.data(ROLE_LEVEL)
            return item_level >= self._level
        else:
            return False

    def set_level(self, level):
        self._level = level
        self.invalidateFilter()


class LogWindow:
    def __init__(self, app):
        self.log_handler = None
        self.app = app
        ui_file = QFile(UI_FILENAME)
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        self.window = loader.load(ui_file)
        combo = self.window.log_level_combo
        combo.clear()
        current = None
        self.icons = []
        root_logger = logging.getLogger()
        current_level = root_logger.getEffectiveLevel()
        for (name, level, icon_name) in LEVELS:
            if icon_name:
                icon = QIcon.fromTheme(icon_name)
            else:
                icon = QIcon()
            self.icons.append((level, icon))
            combo.addItem(name, level)
            if level == current_level:
                current = name
        if current:
            combo.setCurrentText(current)
        self.view = self.window.list
        self.model = QStandardItemModel(self.view)
        self.model.setHorizontalHeaderLabels(["Message"])
        self.proxy = LogFilterProxyModel(self.view, current_level)
        self.proxy.setSourceModel(self.model)
        self.view.setModel(self.proxy)
        self.view.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.view.setIndentation(0)
        self.log_handler = LogHandler(self)
        root_logger.addHandler(self.log_handler)
        self.window.follow_chk.toggled.connect(self.follow_toggled)
        combo.currentIndexChanged.connect(self.level_changed)

    def __del__(self):
        if self.log_handler:
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.log_handler)

    def add_entry(self, msg, level, timestamp):
        logger.debug("add_entry%r", (msg, level, timestamp))
        for icon_level, icon in self.icons:
            if level >= icon_level:
                break
        else:
            icon = QIcon()
        item = QStandardItem(icon, msg)
        item.setData(level, ROLE_LEVEL)
        self.model.appendRow([item])
        if self.window.follow_chk.isChecked():
            self.scroll_to_bottom()
            if self.window.isVisible():
                self.view.repaint()

    def scroll_to_bottom(self):
        index = self.proxy.index(self.proxy.rowCount() - 1, 0)
        self.view.scrollTo(index, QAbstractItemView.PositionAtBottom)

    def follow_toggled(self, enabled):
        if enabled:
            self.scroll_to_bottom()

    def level_changed(self, index=None):
        combo = self.window.log_level_combo
        level = combo.currentData()
        root_logger = logging.getLogger()
        if level <= logging.DEBUG:
            root_logger.setLevel(level)
        else:
            # log everything >= INFO, just filter accordingly
            root_logger.setLevel(logging.INFO)
        self.proxy.set_level(level)

    def close(self):
        if self.window:
            self.window.close()
