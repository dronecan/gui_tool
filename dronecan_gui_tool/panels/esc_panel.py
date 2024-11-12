#
# Copyright (C) 2016  UAVCAN Development Team  <uavcan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

import dronecan
from functools import partial
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QWidget, QLabel, QDialog, QSlider, QSpinBox, QDoubleSpinBox, \
    QPlainTextEdit, QCheckBox
from PyQt5.QtCore import QTimer, Qt
from logging import getLogger
from ..widgets import make_icon_button, get_icon, get_monospace_font
import sip
import time

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'ESC Panel'


logger = getLogger(__name__)

_singleton = None


class PercentSlider(QWidget):
    def __init__(self, esc_index, parent):
        super(PercentSlider, self).__init__(parent)

        self._index = esc_index

        self._slider = QSlider(Qt.Vertical, self)
        self._slider.setMinimum(-100)
        self._slider.setMaximum(100)
        self._slider.setValue(0)
        self._slider.setTickInterval(100)
        self._slider.setTickPosition(QSlider.TicksBothSides)
        self._slider.valueChanged.connect(lambda: self._spinbox.setValue(self._slider.value()))

        self._spinbox = QSpinBox(self)
        self._spinbox.setMinimum(-100)
        self._spinbox.setMaximum(100)
        self._spinbox.setValue(0)
        self._spinbox.valueChanged.connect(lambda: self._slider.setValue(self._spinbox.value()))

        self._zero_button = make_icon_button('hand-stop-o', 'Zero setpoint', self, on_clicked=self.zero)

        self._index_label = QLabel(f'Index: {self._index}', self)
        self._error_count_label = QLabel('Err: NC', self)
        self._voltage_label = QLabel('Volt: NC', self)
        self._current_label = QLabel('Curr: NC', self)
        self._temperature_label = QLabel('Temp: NC', self)
        self._rpm_label = QLabel('RPM: NC', self)
        self._power_rating_pct_label = QLabel('RAT: NC', self)

        layout = QHBoxLayout(self)

        status_layout = QVBoxLayout(self)
        status_layout.addWidget(self._index_label)
        status_layout.addWidget(self._error_count_label)
        status_layout.addWidget(self._voltage_label)
        status_layout.addWidget(self._current_label)
        status_layout.addWidget(self._temperature_label)
        status_layout.addWidget(self._rpm_label)
        status_layout.addWidget(self._power_rating_pct_label)
        status_layout.addStretch()
        status_layout.addWidget(self._spinbox)
        status_layout.addWidget(self._zero_button)

        layout.addLayout(status_layout)
        layout.addWidget(self._slider)

        self.setLayout(layout)

    def zero(self):
        self._slider.setValue(0)

    def get_value(self):
        return self._slider.value()
    
    def update_view_mode_ui(self, enable):
        self._slider.setEnabled(not enable)
        self._spinbox.setEnabled(not enable)
        self._zero_button.setEnabled(not enable)

    def view_mode_set_value(self, value):
        if not self._slider.isEnabled() and not self._spinbox.isEnabled() and not self._zero_button.isEnabled():
            self._slider.setValue(value)
            self._spinbox.setValue(value)

    def update_status(self, msg):
        status = msg.message
        if status.esc_index == self._index:
            self._error_count_label.setText(f'Err: {status.error_count}')
            self._voltage_label.setText(f'Volt: {status.voltage:.1f} V')
            self._current_label.setText(f'Curr: {status.current:.1f} A')
            temperature_celsius = status.temperature - 273.15
            self._temperature_label.setText(f'Temp: {temperature_celsius:.1f} °C')
            self._rpm_label.setText(f'RPM: {status.rpm}')
            self._power_rating_pct_label.setText(f'RAT: {status.power_rating_pct} %')


class ESCPanel(QDialog):
    DEFAULT_RATE = 10

    CMD_BIT_LENGTH = dronecan.get_dronecan_data_type(dronecan.uavcan.equipment.esc.RawCommand().cmd).value_type.bitlen
    CMD_MAX = 2 ** (CMD_BIT_LENGTH - 1) - 1
    CMD_MIN = -(2 ** (CMD_BIT_LENGTH - 1))

    def __init__(self, parent, node):
        super(ESCPanel, self).__init__(parent)
        self.setWindowTitle('ESC Management Panel')
        self.setAttribute(Qt.WA_DeleteOnClose)              # This is required to stop background timers!

        self._node = node

        self._view_mode = QCheckBox(self)
        self._view_mode_label = QLabel('View Mode Inactive', self)
        self._view_mode_external_source_label = QLabel('', self)
        self._view_mode_external_detect_timestamp = 0

        self._sliders = [PercentSlider(index, self) for index in range(4)]

        self._num_sliders = QSpinBox(self)
        self._num_sliders.setMinimum(len(self._sliders))
        self._num_sliders.setMaximum(20)
        self._num_sliders.setValue(len(self._sliders))
        self._num_sliders.valueChanged.connect(self._update_number_of_sliders)

        self._safety_enable = QCheckBox(self)
        self._arming_enable = QCheckBox(self)

        self._bcast_rate = QSpinBox(self)
        self._bcast_rate.setMinimum(1)
        self._bcast_rate.setMaximum(500)
        self._bcast_rate.setSingleStep(1)
        self._bcast_rate.setValue(self.DEFAULT_RATE)
        self._bcast_rate.valueChanged.connect(
            lambda: self._bcast_timer.setInterval(int(1e3 / self._bcast_rate.value())))

        self._stop_all = make_icon_button('hand-stop-o', 'Zero all channels', self, text='Stop All',
                                          on_clicked=self._do_stop_all)

        self._pause = make_icon_button('pause', 'Pause publishing', self, checkable=True, text='Pause')

        self._msg_viewer = QPlainTextEdit(self)
        self._msg_viewer.setReadOnly(True)
        self._msg_viewer.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._msg_viewer.setFont(get_monospace_font())
        self._msg_viewer.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._msg_viewer.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self._bcast_timer = QTimer(self)
        self._bcast_timer.start(int(1e3 / self.DEFAULT_RATE))
        self._bcast_timer.timeout.connect(self._do_broadcast)

        layout = QVBoxLayout(self)

        self._mode_layout = QHBoxLayout(self)
        self._mode_layout.addWidget(self._view_mode)
        self._mode_layout.addWidget(self._view_mode_label)
        self._mode_layout.addWidget(self._view_mode_external_source_label)
        self._mode_layout.setAlignment(Qt.AlignCenter)
        layout.addLayout(self._mode_layout)

        self._slider_layout = QHBoxLayout(self)
        for sl in self._sliders:
            self._slider_layout.addWidget(sl)
        layout.addLayout(self._slider_layout)

        layout.addWidget(self._stop_all)

        controls_layout = QHBoxLayout(self)
        controls_layout.addWidget(QLabel('Channels:', self))
        controls_layout.addWidget(self._num_sliders)
        controls_layout.addWidget(QLabel('SendSafety:', self))
        controls_layout.addWidget(self._safety_enable)
        controls_layout.addWidget(QLabel('SendArming:', self))
        controls_layout.addWidget(self._arming_enable)
        controls_layout.addWidget(QLabel('Broadcast Rate:', self))
        controls_layout.addWidget(self._bcast_rate)
        controls_layout.addWidget(QLabel('Hz', self))
        controls_layout.addStretch()
        controls_layout.addWidget(self._pause)
        layout.addLayout(controls_layout)

        layout.addWidget(QLabel('Generated message:', self))
        layout.addWidget(self._msg_viewer)

        self.setLayout(layout)
        self.resize(self.minimumWidth(), self.minimumHeight())

        self._node.add_handler(dronecan.uavcan.equipment.esc.Status, self._on_esc_status)
        self._node.add_handler(dronecan.uavcan.equipment.esc.RawCommand, self._on_esc_raw_command)
    
    def _on_esc_status(self, msg):
        if msg.message.esc_index < len(self._sliders):
            sl = self._sliders[msg.message.esc_index] 
            if sl and not sip.isdeleted(sl):
                sl.update_status(msg)

    def _on_esc_raw_command(self, msg):
        if msg.transfer.source_node_id is not self._node.node_id:
            self._view_mode_external_detect_timestamp = int(time.time() * 1000)
            self._view_mode_external_source_label.setText(f'(External Source ID: {msg.transfer.source_node_id})')
            self._view_mode.setEnabled(False)
            self._view_mode.setChecked(True)
            raw_command = msg.message
            for i, sl in enumerate(self._sliders):
                cmd_raw_value = raw_command.cmd[i]
                if cmd_raw_value >= 0:
                    sl.view_mode_set_value(int((cmd_raw_value / self.CMD_MAX) * 100))
                else:
                    sl.view_mode_set_value(int((cmd_raw_value / self.CMD_MIN) * -100))

            self._msg_viewer.setPlainText(dronecan.to_yaml(msg))

    def _update_view_mode(self):
        if not self._view_mode.isEnabled() and int(time.time() * 1000) - self._view_mode_external_detect_timestamp > 2000:
            self._view_mode.setEnabled(True) # release view mode checkbox after 2s timeout from external source

        view_mode_enabled = self._view_mode.isChecked()
        self._stop_all.setEnabled(not view_mode_enabled)
        self._safety_enable.setEnabled(not view_mode_enabled)
        self._pause.setEnabled(not view_mode_enabled)
        self._arming_enable.setEnabled(not view_mode_enabled)
        self._bcast_rate.setEnabled(not view_mode_enabled)
        for sl in self._sliders:
            sl.update_view_mode_ui(view_mode_enabled)

        if view_mode_enabled:
            self._view_mode_label.setText('View Mode Active')
        else:
            self._view_mode_label.setText('View Mode Inactive')
            self._view_mode_external_source_label.setText('')

    def _do_broadcast(self):
        try:
            self._update_view_mode()
            if not self._view_mode.isChecked():
                if not self._pause.isChecked():
                    if self._safety_enable.checkState():
                        msg = dronecan.ardupilot.indication.SafetyState()
                        msg.status = msg.STATUS_SAFETY_OFF
                        self._node.broadcast(msg)
                    if self._arming_enable.checkState():
                        msg = dronecan.uavcan.equipment.safety.ArmingStatus()
                        msg.status = msg.STATUS_FULLY_ARMED
                        self._node.broadcast(msg)
                    msg = dronecan.uavcan.equipment.esc.RawCommand()
                    for sl in self._sliders:
                        raw_value = sl.get_value() / 100
                        value = (-self.CMD_MIN if raw_value < 0 else self.CMD_MAX) * raw_value
                        msg.cmd.append(int(value))

                    self._node.broadcast(msg)
                    self._msg_viewer.setPlainText(dronecan.to_yaml(msg))
                else:
                    self._msg_viewer.setPlainText('Paused')
        except Exception as ex:
            self._msg_viewer.setPlainText('Publishing failed:\n' + str(ex))

    def _do_stop_all(self):
        for sl in self._sliders:
            sl.zero()

    def _update_number_of_sliders(self):
        num_sliders = self._num_sliders.value()

        while len(self._sliders) > num_sliders:
            removee = self._sliders[-1]
            self._sliders = self._sliders[:-1]
            self._slider_layout.removeWidget(removee)
            removee.close()
            removee.deleteLater()

        while len(self._sliders) < num_sliders:
            new = PercentSlider(len(self._sliders), self)
            self._slider_layout.addWidget(new)
            self._sliders.append(new)

        def deferred_resize():
            self.resize(self.minimumWidth(), self.height())

        deferred_resize()
        # noinspection PyCallByClass,PyTypeChecker
        QTimer.singleShot(200, deferred_resize)

    def __del__(self):
        global _singleton
        _singleton = None

    def closeEvent(self, event):
        global _singleton
        _singleton = None
        super(ESCPanel, self).closeEvent(event)


def spawn(parent, node):
    global _singleton
    if _singleton is None:
        _singleton = ESCPanel(parent, node)

    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()

    return _singleton


get_icon = partial(get_icon, 'asterisk')
