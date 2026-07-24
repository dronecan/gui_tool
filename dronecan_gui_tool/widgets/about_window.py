#
# Copyright (C) 2016  UAVCAN Development Team  <uavcan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

import dronecan
try:
    from ..version import __version_tuple__
except ImportError:
    __version_tuple__ = (0, 0, 0, "unknown")
from . import get_icon, get_app_icon
from PyQt6.QtWidgets import QDialog, QTableWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, \
    QTableWidgetItem, QHeaderView
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt, PYQT_VERSION_STR, QSize

numeric_parts = [x for x in __version_tuple__ if isinstance(x, int)]
metadata_parts = [x for x in __version_tuple__ if isinstance(x, str)]
is_clean_release = len(metadata_parts) == 0
is_dirty = any(".d" in part for part in metadata_parts)
version_info = '.'.join(map(str, numeric_parts))
metadata_info = '.'.join(map(str, metadata_parts))

ABOUT_TEXT = (f"""
<h3>DroneCAN GUI Tool v{version_info}</h3>
{f"<h4>Dev Build {'(Dirty)' if is_dirty else ''}: {metadata_info}</h4>" if not is_clean_release else ""}

<p>Cross-platform application for <a href="http://dronecan.org/">DroneCAN bus</a> management and diagnostics.</p>

<p>This application is distributed under the terms of the MIT software license. The source repository and the bug \
tracker are located at <a href="https://github.com/DroneCAN/gui_tool">https://github.com/DroneCAN/gui_tool</a>.</p>
""")


def _list_3rd_party():
    import pyqtgraph
    import qtawesome

    try:
        from qtconsole import __version__ as qtconsole_version
        from IPython import __version__ as ipython_version
    except ImportError:
        qtconsole_version = 'N/A'
        ipython_version = 'N/A'
    try:
        from pymavlink import __version__ as pymavlink_version
    except ImportError:
        pymavlink_version = 'N/A'

    return [
        ('PyDroneCAN',  dronecan.__version__,   'MIT',      'http://dronecan.org/Implementations/Pydronecan'),
        ('PyQt6',       PYQT_VERSION_STR,       'GPLv3',    'https://www.riverbankcomputing.com/software/pyqt/intro'),
        ('PyQtGraph',   pyqtgraph.__version__,  'MIT',      'http://www.pyqtgraph.org/'),
        ('QtAwesome',   qtawesome.__version__,  'MIT',      'https://github.com/spyder-ide/qtawesome'),
        ('QtConsole',   qtconsole_version,      'BSD',      'http://jupyter.org'),
        ('IPython',     ipython_version,        'BSD',      'https://ipython.org'),
        ('pymavlink',   pymavlink_version,      'LGPLv3+',  'http://github.com/ardupilot/pymavlink'),
    ]


class AboutWindow(QDialog):
    def __init__(self, parent):
        super(AboutWindow, self).__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle('About DroneCAN GUI Tool')

        #
        # Icon
        #
        icon_size = 128
        canvas_size = 150
        pixmap = get_app_icon().pixmap(QSize(icon_size, icon_size), QIcon.Normal, QIcon.On)
        self._icon = QLabel(self)
        self._icon.setPixmap(pixmap)
        self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setMinimumSize(QSize(canvas_size, canvas_size))

        #
        # Description text
        #
        self._description = QLabel(self)
        self._description.setWordWrap(True)
        self._description.setTextFormat(Qt.RichText)
        self._description.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self._description.setOpenExternalLinks(True)
        self._description.setText(ABOUT_TEXT)

        #
        # List of third-party components
        #
        third_party = _list_3rd_party()

        self._components = QTableWidget(self)
        self._components.setShowGrid(False)
        self._components.verticalHeader().setVisible(False)
        self._components.setRowCount(len(third_party))
        self._components.setColumnCount(len(third_party[0]))
        self._components.setWordWrap(False)
        self._components.setHorizontalHeaderLabels(['Component', 'Version', 'License', 'Home page'])

        for row, component in enumerate(third_party):
            for col, field in enumerate(component):
                if field is not None:
                    w = QTableWidgetItem(str(field))
                    w.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self._components.setItem(row, col, w)

        self._components.resizeRowsToContents()
        self._components.resizeColumnsToContents()
        self._components.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)

        #
        # Window layout
        #
        self._exit_button = QPushButton(get_icon('fa6s.check'), 'OK', self)
        self._exit_button.clicked.connect(self.close)

        layout = QVBoxLayout(self)
        top_layout = QHBoxLayout(self)
        top_layout.addWidget(self._icon)
        top_layout.addWidget(self._description, 1)
        layout.addLayout(top_layout)
        layout.addWidget(self._components, 1)
        layout.addWidget(self._exit_button)
        self.setLayout(layout)

        self.setMinimumSize(QSize(600, 300))
        self.resize(QSize(700, 400))
