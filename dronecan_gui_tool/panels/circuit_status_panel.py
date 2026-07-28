#
# Copyright (C) 2026 DroneCAN Development Team <dronecan.org>
#
# This software is distributed under the terms of the MIT License.
#

import dronecan
from functools import partial
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QDialog, QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QBrush, QColor
from logging import getLogger
from ..widgets import get_icon, get_monospace_font

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'CircuitStatus'

logger = getLogger(__name__)

_singleton = None


class CircuitStatusPanel(QDialog):
    def __init__(self, parent, node):
        super(CircuitStatusPanel, self).__init__(parent)
        self.setWindowTitle('CircuitStatus Monitor')
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._node = node

        # Main Layout
        layout = QVBoxLayout(self)

        # ---------------------------------------------------------
        # Monitoring Group Box (CircuitStatus updates)
        # ---------------------------------------------------------
        monitor_group = QGroupBox('Circuit Status Monitor', self)
        monitor_layout = QVBoxLayout()

        self._table = QTableWidget(self)
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(['Circuit', 'Voltage', 'Current', 'Power', 'Status / Errors'])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.verticalHeader().setVisible(False)

        monitor_layout.addWidget(self._table)
        monitor_group.setLayout(monitor_layout)
        layout.addWidget(monitor_group)

        self._circuit_rows = {}

        self.setLayout(layout)
        self.resize(550, 300)

        # Register DroneCAN handler for CircuitStatus
        self._handlers = [
            self._node.add_handler(dronecan.uavcan.equipment.power.CircuitStatus, self._on_circuit_status)
        ]

        # Timer to check for offline/stale status
        self._stale_timer = QTimer(self)
        self._stale_timer.timeout.connect(self._check_stale_circuits)
        self._stale_timer.start(1000)

    def _on_circuit_status(self, event):
        import time
        msg = event.message
        cid = msg.circuit_id

        if cid not in self._circuit_rows:
            # Insert row at sorted position
            row_idx = sum(1 for existing_cid in self._circuit_rows if existing_cid < cid)
            self._table.insertRow(row_idx)

            item_name = QTableWidgetItem(f'Circuit {cid}')
            item_volt = QTableWidgetItem('NC')
            item_curr = QTableWidgetItem('NC')
            item_pwr = QTableWidgetItem('NC')
            item_err = QTableWidgetItem('NC')

            font = get_monospace_font()
            for item in (item_name, item_volt, item_curr, item_pwr, item_err):
                item.setFont(font)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

            self._table.setItem(row_idx, 0, item_name)
            self._table.setItem(row_idx, 1, item_volt)
            self._table.setItem(row_idx, 2, item_curr)
            self._table.setItem(row_idx, 3, item_pwr)
            self._table.setItem(row_idx, 4, item_err)

            self._circuit_rows[cid] = {
                'voltage': item_volt,
                'current': item_curr,
                'power': item_pwr,
                'error': item_err,
                'last_update': 0
            }

        row = self._circuit_rows[cid]
        row['last_update'] = time.time()
        
        # Format voltage, current, power
        v = msg.voltage
        i = msg.current
        p = v * i
        
        row['voltage'].setText(f'{v:6.2f} V')
        row['current'].setText(f'{i:6.2f} A')
        row['power'].setText(f'{p:6.2f} W')

        # Parse error flags
        errs = []
        flags = msg.error_flags
        if flags & msg.ERROR_FLAG_OVERVOLTAGE:
            errs.append('OVER_V')
        if flags & msg.ERROR_FLAG_UNDERVOLTAGE:
            errs.append('UNDER_V')
        if flags & msg.ERROR_FLAG_OVERCURRENT:
            errs.append('OVER_C')
        if flags & msg.ERROR_FLAG_UNDERCURRENT:
            errs.append('UNDER_C')

        if errs:
            row['error'].setText(', '.join(errs))
            row['error'].setForeground(QBrush(QColor('red')))
            font = row['error'].font()
            font.setBold(True)
            row['error'].setFont(font)
        else:
            row['error'].setText('OK')
            row['error'].setForeground(QBrush(QColor('green')))
            font = row['error'].font()
            font.setBold(False)
            row['error'].setFont(font)

    def _check_stale_circuits(self):
        import time
        now = time.time()
        for cid, row in self._circuit_rows.items():
            if row['last_update'] == 0:
                continue
            if now - row['last_update'] > 3.0:
                row['voltage'].setText('STALE')
                row['current'].setText('STALE')
                row['power'].setText('STALE')
                row['error'].setText('OFFLINE')
                row['error'].setForeground(QBrush(QColor('gray')))
                font = row['error'].font()
                font.setBold(False)
                row['error'].setFont(font)

    def __del__(self):
        global _singleton
        _singleton = None
        for h in self._handlers:
            try:
                h.remove()
            except Exception:
                pass

    def closeEvent(self, event):
        global _singleton
        _singleton = None
        for h in self._handlers:
            try:
                h.remove()
            except Exception:
                pass
        super(CircuitStatusPanel, self).closeEvent(event)


def spawn(parent, node):
    global _singleton
    if _singleton is None:
        _singleton = CircuitStatusPanel(parent, node)

    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()

    return _singleton


get_icon = partial(get_icon, 'fa6s.asterisk')
