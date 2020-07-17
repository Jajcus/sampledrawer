
import os

from PySide2.QtUiTools import QUiLoader
from PySide2.QtCore import QFile

from .filebrowser import FileBrowser
from .sampleplayer import SamplePlayer

from . import __path__ as PKG_PATH

UI_FILENAME = os.path.join(PKG_PATH[0], "mainwindow.ui")

class MainWindow:
    def __init__(self):
        ui_file = QFile(UI_FILENAME)
        ui_file.open(QFile.ReadOnly)
        loader = QUiLoader()
        self.window = loader.load(ui_file)
        self.file_browser = FileBrowser(self.window.file_tree)
        self.sample_player = SamplePlayer(self.window)
        self.file_browser.file_selected.connect(self.sample_player.file_selected)
    def show(self):
        self.window.show()
