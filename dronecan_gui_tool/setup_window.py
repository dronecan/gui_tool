#
# Copyright (C) 2016  UAVCAN Development Team  <uavcan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

import sys
import glob
import time
import threading
import copy
from .widgets import show_error, get_monospace_font
from PyQt5.QtWidgets import QComboBox, QCompleter, QDialog, QDirModel, QFileDialog, QGroupBox, QHBoxLayout, QLabel, \
    QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QGridLayout, QCheckBox
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIntValidator
from logging import getLogger
from collections import OrderedDict
from itertools import count


STANDARD_BAUD_RATES = 9600, 115200, 460800, 921600, 1000000, 3000000
DEFAULT_BAUD_RATE = 115200
assert DEFAULT_BAUD_RATE in STANDARD_BAUD_RATES


RUNNING_ON_LINUX = 'linux' in sys.platform.lower()


logger = getLogger(__name__)


def _linux_parse_proc_net_dev(out_ifaces):
    with open('/proc/net/dev') as f:
        for line in f:
            if ':' in line:
                name = line.split(':')[0].strip()
                out_ifaces.insert(0 if 'can' in name else len(out_ifaces), name)
    return out_ifaces


def _linux_parse_ip_link_show(out_ifaces):
    import re
    import subprocess
    import tempfile

    with tempfile.TemporaryFile() as f:
        proc = subprocess.Popen('ip link show', shell=True, stdout=f)
        if 0 != proc.wait(10):
            raise RuntimeError('Process failed')
        f.seek(0)
        out = f.read().decode()

    return re.findall(r'\d+?: ([a-z0-9]+?): <[^>]*UP[^>]*>.*\n *link/can', out) + out_ifaces

def _mavcan_interfaces():
    '''extra CAN over mavlink interfaces'''
    try:
        from pymavlink import mavutil
    except ImportError:
        return []
    return ['mavcan::14550']

def list_ifaces():
    """Returns dictionary, where key is description, value is the OS assigned name of the port"""
    logger.debug('Updating iface list...')
    if RUNNING_ON_LINUX:
        # Linux system
        ifaces = glob.glob('/dev/serial/by-id/*')
        try:
            ifaces = list(sorted(ifaces,
                                 key=lambda s: not ('zubax' in s.lower() and 'babel' in s.lower())))
        except Exception:
            logger.warning('Sorting failed', exc_info=True)

        # noinspection PyBroadException
        try:
            ifaces = _linux_parse_ip_link_show(ifaces)       # Primary
        except Exception as ex:
            logger.warning('Could not parse "ip link show": %s', ex, exc_info=True)
            ifaces = _linux_parse_proc_net_dev(ifaces)       # Fallback

        ifaces += _mavcan_interfaces()

        out = OrderedDict()
        for x in ifaces:
            out[x] = x

        return out
    else:
        # Windows, Mac, whatever
        from PyQt5 import QtSerialPort

        out = OrderedDict()
        for port in QtSerialPort.QSerialPortInfo.availablePorts():
            if sys.platform == 'darwin':
                if 'tty' in port.systemLocation():
                    out[port.systemLocation()] = port.systemLocation()
            else:
                out[port.description()] = port.systemLocation()

        mifaces = _mavcan_interfaces()
        for x in mifaces:
            out[x] = x

        return out


class BackgroundIfaceListUpdater:
    UPDATE_INTERVAL = 0.5

    def __init__(self):
        self._ifaces = list_ifaces()
        self._thread = threading.Thread(target=self._run, name='iface_lister', daemon=True)
        self._keep_going = True
        self._lock = threading.Lock()

    def __enter__(self):
        logger.debug('Starting iface list updater')
        self._thread.start()
        return self

    def __exit__(self, *_):
        logger.debug('Stopping iface list updater...')
        self._keep_going = False
        self._thread.join()
        logger.debug('Stopped iface list updater')

    def _run(self):
        while self._keep_going:
            time.sleep(self.UPDATE_INTERVAL)
            new_list = list_ifaces()
            with self._lock:
                self._ifaces = new_list

    def get_list(self):
        with self._lock:
            return copy.copy(self._ifaces)


class DirectorySelectionWidget(QGroupBox):
    def __init__(self, parent, dsdl_path=None):
        super(DirectorySelectionWidget, self).__init__('Location of custom DSDL definitions [optional]', parent)
        self._dir_selection = dsdl_path
        dir_textbox = QLineEdit(self)
        dir_textbox.setText(self._dir_selection)

        dir_text_completer = QCompleter(self)
        dir_text_completer.setCaseSensitivity(Qt.CaseSensitive)
        dir_text_completer.setModel(QDirModel(self))
        dir_textbox.setCompleter(dir_text_completer)

        def on_edit():
            self._dir_selection = str(dir_textbox.text())

        dir_textbox.textChanged.connect(on_edit)

        dir_browser = QPushButton('Browse', self)

        def on_browse():
            self._dir_selection = str(QFileDialog.getExistingDirectory(self, 'Select Directory'))
            dir_textbox.setText(self._dir_selection)

        dir_browser.clicked.connect(on_browse)

        layout = QHBoxLayout(self)
        layout.addWidget(dir_textbox)
        layout.addWidget(dir_browser)
        self.setLayout(layout)

    def get_selection(self):
        return self._dir_selection


def run_setup_window(icon, dsdl_path=None):
    win = QDialog()
    win.setWindowTitle('Application Setup')
    win.setWindowIcon(icon)
    win.setWindowFlags(Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
    win.setAttribute(Qt.WA_DeleteOnClose)              # This is required to stop background timers!

    combo = QComboBox(win)
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
    combo.setFont(get_monospace_font())

    combo_completer = QCompleter()
    combo_completer.setCaseSensitivity(Qt.CaseSensitive)
    combo_completer.setModel(combo.model())
    combo.setCompleter(combo_completer)

    bitrate = QSpinBox(win)
    bitrate.setMaximum(1000000)
    bitrate.setMinimum(10000)
    bitrate.setValue(1000000)

    bus_number = QSpinBox(win)
    bus_number.setMaximum(4)
    bus_number.setMinimum(1)
    bus_number.setValue(1)
    
    baudrate = QComboBox(win)
    baudrate.setEditable(True)
    baudrate.setInsertPolicy(QComboBox.NoInsert)
    baudrate.setSizeAdjustPolicy(QComboBox.AdjustToContents)
    baudrate.setFont(get_monospace_font())

    baudrate_completer = QCompleter(win)
    baudrate_completer.setModel(baudrate.model())
    baudrate.setCompleter(baudrate_completer)

    baudrate.setValidator(QIntValidator(min(STANDARD_BAUD_RATES), max(STANDARD_BAUD_RATES)))
    baudrate.insertItems(0, map(str, STANDARD_BAUD_RATES))
    baudrate.setCurrentText(str(DEFAULT_BAUD_RATE))

    filtered = QCheckBox('Enable Filtering')

    dir_selection = DirectorySelectionWidget(win, dsdl_path)

    ok = QPushButton('OK', win)

    ifaces = None

    def update_iface_list():
        nonlocal ifaces
        ifaces = iface_lister.get_list()
        known_keys = set()
        remove_indices = []
        was_empty = combo.count() == 0
        # Marking known and scheduling for removal
        for idx in count():
            tx = combo.itemText(idx)
            if not tx:
                break
            known_keys.add(tx)
            if tx not in list(ifaces.keys()):
                logger.debug('Removing iface %r', tx)
                remove_indices.append(idx)
        # Removing - starting from the last item in order to retain indexes
        for idx in remove_indices[::-1]:
            combo.removeItem(idx)
        # Adding new items - starting from the last item in order to retain the final order
        for key in list(ifaces.keys())[::-1]:
            if key and key not in known_keys:
                logger.debug('Adding iface %r', key)
                combo.insertItem(0, key)
        # Updating selection
        if was_empty:
            combo.setCurrentIndex(0)

    result = None
    kwargs = {}

    def on_ok():
        nonlocal result, kwargs
        try:
            baud_rate_value = int(baudrate.currentText())
        except ValueError:
            show_error('Invalid parameters', 'Could not parse baud rate', 'Please specify correct baud rate',
                       parent=win)
            return
        if not (min(STANDARD_BAUD_RATES) <= baud_rate_value <= max(STANDARD_BAUD_RATES)):
            show_error('Invalid parameters', 'Baud rate is out of range',
                       'Baud rate value should be within [%s, %s]' %
                       (min(STANDARD_BAUD_RATES), max(STANDARD_BAUD_RATES)),
                       parent=win)
            return
        kwargs['baudrate'] = baud_rate_value
        kwargs['bitrate'] = int(bitrate.value())
        kwargs['bus_number'] = int(bus_number.value())
        kwargs['filtered'] = filtered.checkState()
        result_key = str(combo.currentText()).strip()
        if not result_key:
            show_error('Invalid parameters', 'Interface name cannot be empty', 'Please select a valid interface',
                       parent=win)
            return
        try:
            result = ifaces[result_key]
        except KeyError:
            result = result_key
        win.close()

    ok.clicked.connect(on_ok)

    can_group = QGroupBox('CAN interface setup', win)
    can_layout = QVBoxLayout()
    can_layout.addWidget(QLabel('Select CAN interface'))
    can_layout.addWidget(combo)

    adapter_group = QGroupBox('Adapter settings', win)
    adapter_layout = QGridLayout()
    adapter_layout.addWidget(QLabel('Bus Number:'), 0, 0)
    adapter_layout.addWidget(bus_number, 0, 1)
    adapter_layout.addWidget(QLabel('CAN bus bit rate:'), 1, 0)
    adapter_layout.addWidget(bitrate, 1, 1)
    adapter_layout.addWidget(QLabel('Adapter baud rate (not applicable to USB):'), 2, 0)
    adapter_layout.addWidget(baudrate, 2, 1)
    adapter_layout.addWidget(QLabel('Filter for low bandwidth:'), 3, 0)
    adapter_layout.addWidget(filtered, 3, 1)

    adapter_group.setLayout(adapter_layout)

    can_layout.addWidget(adapter_group)
    can_group.setLayout(can_layout)

    layout = QVBoxLayout()
    layout.addWidget(can_group)
    layout.addWidget(dir_selection)
    layout.addWidget(ok)
    layout.setSizeConstraint(layout.SetFixedSize)
    win.setLayout(layout)

    with BackgroundIfaceListUpdater() as iface_lister:
        update_iface_list()
        timer = QTimer(win)
        timer.setSingleShot(False)
        timer.timeout.connect(update_iface_list)
        timer.start(int(BackgroundIfaceListUpdater.UPDATE_INTERVAL / 2 * 1000))
        win.exec()

    return result, kwargs, dir_selection.get_selection()
