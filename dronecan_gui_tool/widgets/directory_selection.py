from PyQt5.QtWidgets import QGroupBox, QLineEdit, QCompleter, QPushButton, QDirModel, QHBoxLayout, QFileDialog
from PyQt5.QtCore import Qt

class DirectorySelectionWidget(QGroupBox):
    def __init__(self, parent, label, path=None, directory_only=False):
        super(DirectorySelectionWidget, self).__init__(label, parent)
        self._selection = path
        dir_textbox = QLineEdit(self)
        dir_textbox.setText(self._selection)

        dir_text_completer = QCompleter(self)
        dir_text_completer.setCaseSensitivity(Qt.CaseSensitive)
        dir_text_completer.setModel(QDirModel(self))
        dir_textbox.setCompleter(dir_text_completer)

        def on_edit():
            self._selection = str(dir_textbox.text())

        dir_textbox.textChanged.connect(on_edit)

        dir_browser = QPushButton('Browse', self)

        def on_browse():
            if directory_only:
                self._selection = str(QFileDialog.getExistingDirectory(self, 'Select Directory'))
            else:
                self._selection = QFileDialog.getOpenFileName(self, 'Select File')[0]
            dir_textbox.setText(self._selection)

        dir_browser.clicked.connect(on_browse)

        layout = QHBoxLayout(self)
        layout.addWidget(dir_textbox)
        layout.addWidget(dir_browser)
        self.setLayout(layout)

    def get_selection(self):
        return self._selection
