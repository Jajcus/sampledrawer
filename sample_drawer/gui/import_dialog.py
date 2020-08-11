
import logging
import os

from functools import partial

from PySide2.QtCore import Qt, QFile, QItemSelection, QRegExp, QTimer
from PySide2.QtUiTools import QUiLoader
from PySide2.QtWidgets import QDialogButtonBox, QAbstractItemView
from PySide2.QtGui import QStandardItemModel, QIcon, QStandardItem, QRegExpValidator

from ..library import LibraryConflictError

from . import __path__ as PKG_PATH


# Qt regexp, must match Python regexp VALID_TAG_RE from metadata.py
TAG_LIST_REGEXP = r"^(((/[\w-]+)*/)?[\w-]+)?([ ;,]+((/[\w-]+)*/)?[\w-]+)*$"


logger = logging.getLogger("import_dialog")

UI_FILENAME = os.path.join(PKG_PATH[0], "import_dialog.ui")

class ImportDialog:
    def __init__(self, main_window):
        self.main_window = main_window
        self.app = main_window.app
        self.items = []
        self.extra_tags = []
        self.loading = False
        self.exitting = False
        self.rewrite_rules = None
        ui_file = QFile(UI_FILENAME)
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        self.window = loader.load(ui_file, main_window.window)
        self.window.setModal(True)
        self.preview = self.window.preview
        self.preview_model = QStandardItemModel()
        self.preview_model.setColumnCount(3)
        self.set_preview_header()
        self.preview.setHeaderHidden(False)
        self.preview.setIndentation(0)
        self.preview.setModel(self.preview_model)
        self.preview.sortByColumn(0, Qt.AscendingOrder)
        self.preview.setDragEnabled(False)
        self.preview.setAcceptDrops(False)
        self.preview.setSortingEnabled(True)
        self.preview.setSelectionMode(QAbstractItemView.NoSelection)
        self.preview.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.preview_timer = QTimer(self.window)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.update_preview)
        tags_input = self.window.extra_tags_input
        validator = QRegExpValidator(QRegExp(TAG_LIST_REGEXP), tags_input)
        tags_input.setValidator(validator)
        tags_input.textEdited.connect(self.tags_input_edited)
        buttons = self.window.buttons
        self.ok_button = buttons.button(QDialogButtonBox.Ok)
        self.cancel_button = buttons.button(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.ok_clicked)
        buttons.rejected.connect(self.cancel_clicked)
        combo = self.rewrite_rules_combo = self.window.rewrite_rules_combo
        rules = [(rule["name"], key)
                    for key, rule
                    in self.app.config["rewrite_rules"].items()]
        rules.sort()
        for label, key in rules:
            combo.addItem(label, key)
        default_index = combo.findData("default")
        combo.setCurrentIndex(default_index)
        self.rules_selected_changed(default_index)
        combo.currentIndexChanged.connect(self.rules_selected_changed)

    def rules_selected_changed(self, index):
        key = self.rewrite_rules_combo.itemData(index)
        self.rewrite_rules = self.app.config["rewrite_rules"][key]["rules"]

    def tags_input_edited(self, text):
        tags_input = self.window.extra_tags_input
        if tags_input.hasAcceptableInput():
            text = text.replace(",", "").replace(";", "")
            self.extra_tags = text.split()
            self.preview_timer.start(600)
        self.enable_disable_ok()

    def enable_disable_ok(self):
        tags_input = self.window.extra_tags_input
        if self.loading or not tags_input.hasAcceptableInput():
            self.ok_button.setEnabled(False)
        else:
            self.ok_button.setEnabled(True)

    def load_files(self, paths, root, base_folder="/"):
        logger.debug("load_files%r", (paths, root, base_folder))
        if not root:
            root = "/"
        self.items = []
        self.extra_tags = []
        self.loading = True
        self.ok_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.window.root_input.setText(root)
        self.window.root_tag_input.setText(base_folder)
        self.window.show()

        self.app.qapp.setOverrideCursor(Qt.WaitCursor)
        self.app.qapp.processEvents()
        paths = sorted(paths)
        path, paths = paths[0], paths[1:]
        logger.debug("requesting %r", path)
        callback = partial(self._add_file_metadata, remaining=paths)
        self.main_window.file_analyzer.request_file_metadata(path, callback)
        self.cancel_button.setEnabled(True)
        self.window.exec_()

    def _add_file_metadata(self, path, metadata, remaining):
        logger.debug("_add_file_metadata%r", (path, metadata, remaining))
        if self.exitting:
            return
        if metadata:
            self.items.append((path, metadata))
            self.add_preview_item(path, metadata)
        if remaining:
            self.app.qapp.processEvents()
            callback = partial(self._add_file_metadata,
                               remaining=remaining[1:])
            self.main_window.file_analyzer.request_file_metadata(remaining[0],
                                                                 callback)
        else:
            logger.debug("all files added")
            self.preview.resizeColumnToContents(1)
            self.preview.resizeColumnToContents(0)
            self.app.qapp.restoreOverrideCursor()
            self.loading = False
            self.enable_disable_ok()

    def load_workplace_items(self, items, root="/"):
        self.window.show()

    def update_preview(self):
        self.preview_model.clear()
        self.set_preview_header()
        for path, metadata in self.items:
            self.add_preview_item(path, metadata)
        self.preview.resizeColumnToContents(1)
        self.preview.resizeColumnToContents(0)

    def set_preview_header(self):
        self.preview_model.setHorizontalHeaderLabels(["Name", "Tags", "File"])

    def add_preview_item(self, path, metadata):
        root = self.window.root_input.text()
        metadata = metadata.rewrite(self.rewrite_rules, root=root)
        metadata.add_tags(self.extra_tags)
        item1 = QStandardItem(metadata.name)
        item2 = QStandardItem(", ".join(metadata.get_tags()))
        item3 = QStandardItem(str(path))
        self.preview_model.appendRow([item1, item2, item3])

    def ok_clicked(self):
        logger.debug("OK clicked")
        self.exitting = True
        self.cancel_button.setEnabled(False)
        self.ok_button.setEnabled(False)
        self.app.qapp.setOverrideCursor(Qt.WaitCursor)
        try:
            root = self.window.root_input.text()
            for path, metadata in self.items:
                metadata = metadata.rewrite(self.rewrite_rules, root=root)
                metadata.add_tags(self.extra_tags)
                try:
                    self.app.library.import_file(metadata)
                except LibraryConflictError as err:
                    logger.info("File %r (%r) already in the library, known as %r."
                            " Ignoring it.", path, err.md5, err.existing_name)
        finally:
            self.app.qapp.restoreOverrideCursor()
            self.window.close()

    def cancel_clicked(self):
        logger.debug("Cancel clicked")
        self.exitting = True
        self.app.qapp.restoreOverrideCursor()
        self.window.close()

