#
# Copyright (C) 2026 DroneCAN Development Team <dronecan.org>
#
# This software is distributed under the terms of the MIT License.
#

import dronecan
from functools import partial
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QDialog, QSpinBox, QComboBox, QGroupBox, QLayout
from PyQt6.QtCore import Qt
from logging import getLogger
from ..widgets import make_icon_button, get_icon

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'Hardpoints'

logger = getLogger(__name__)

_singleton = None


class HardpointsPanel(QDialog):
    def __init__(self, parent, node):
        super(HardpointsPanel, self).__init__(parent)
        self.setWindowTitle('Hardpoints Control')
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._node = node

        # Main Layout
        layout = QVBoxLayout(self)

        # ---------------------------------------------------------
        # Control Group Box (Relay/Hardpoint Controls)
        # ---------------------------------------------------------
        control_group = QGroupBox('Relay / Hardpoint Control', self)
        control_layout = QVBoxLayout()

        # Hardpoint ID field
        hp_id_layout = QHBoxLayout()
        hp_id_layout.addWidget(QLabel('Hardpoint ID:', self))
        self._hardpoint_id = QSpinBox(self)
        self._hardpoint_id.setMinimum(0)
        self._hardpoint_id.setMaximum(255)
        self._hardpoint_id.setValue(0)
        hp_id_layout.addWidget(self._hardpoint_id)
        hp_id_layout.addStretch()
        control_layout.addLayout(hp_id_layout)

        # Command / State field
        state_layout = QHBoxLayout()
        state_layout.addWidget(QLabel('State / Command:', self))
        self._state_combo = QComboBox(self)
        self._state_combo.addItem('0 - Release / OFF', 0)
        self._state_combo.addItem('1 - Hold / ON', 1)
        self._state_combo.addItem('Custom...', -1)
        self._state_combo.currentIndexChanged.connect(self._on_state_combo_changed)
        state_layout.addWidget(self._state_combo)

        self._custom_val = QSpinBox(self)
        self._custom_val.setMinimum(0)
        self._custom_val.setMaximum(65535)
        self._custom_val.setValue(0)
        self._custom_val.setVisible(False)
        state_layout.addWidget(self._custom_val)
        state_layout.addStretch()
        control_layout.addLayout(state_layout)

        # Send Button
        self._send_button = make_icon_button('fa6s.paper-plane', 'Send command', self, text='Send Command', on_clicked=self._do_send)
        control_layout.addWidget(self._send_button)

        # Status Label
        self._status_label = QLabel('', self)
        control_layout.addWidget(self._status_label)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        self.setLayout(layout)
        self.setMinimumWidth(350)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

    def _on_state_combo_changed(self):
        is_custom = self._state_combo.currentData() == -1
        self._custom_val.setVisible(is_custom)

    def get_command_value(self):
        val = self._state_combo.currentData()
        if val == -1:
            return self._custom_val.value()
        return val

    def _do_send(self):
        try:
            # Construct the message (uses default ID 1070)
            msg = dronecan.uavcan.equipment.hardpoint.Command()
            msg.hardpoint_id = self._hardpoint_id.value()
            msg.command = self.get_command_value()

            # Broadcast
            self._node.broadcast(msg)

            cmd_val = msg.command
            if cmd_val == 0:
                cmd_str = "release"
            elif cmd_val == 1:
                cmd_str = "hold"
            else:
                cmd_str = str(cmd_val)

            self._status_label.setText(f"command {cmd_str} sent to hardpoint {msg.hardpoint_id}")
        except Exception as ex:
            logger.error(f'Sending failed: {ex}')
            self._status_label.setText(f"Sending failed: {ex}")

    def __del__(self):
        global _singleton
        _singleton = None

    def closeEvent(self, event):
        global _singleton
        _singleton = None
        super(HardpointsPanel, self).closeEvent(event)


def spawn(parent, node):
    global _singleton
    if _singleton is None:
        _singleton = HardpointsPanel(parent, node)

    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()

    return _singleton


get_icon = partial(get_icon, 'fa6s.toggle-on')
