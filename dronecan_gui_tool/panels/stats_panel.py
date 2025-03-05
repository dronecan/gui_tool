#
# Copyright (C) 2023 DroneCAN Development Team <dronecan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Siddharth Purohit
#

import dronecan
from functools import partial
from PyQt5.QtWidgets import QGridLayout, QWidget, QLabel, QDialog, \
     QVBoxLayout, QGroupBox, QLineEdit, QPushButton
from PyQt5.QtCore import Qt, QTimer
from ..widgets import get_icon
from ..widgets import table_display
from . import rtcm3
import time
import socket
import errno

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'Stats Panel'

_singleton = None

class StatsPanel(QDialog):
    def __init__(self, parent, node):
        super(StatsPanel, self).__init__(parent)
        self.setWindowTitle('Stats Panel')
        self.setAttribute(Qt.WA_DeleteOnClose)              # This is required to stop background timers!

        layout = QVBoxLayout()

        self.dronecan_stats_table = table_display.TableDisplay(['Node ID', 'Tx Frames', 'Tx Errors', 'Rx Frames', 'Rx Error OOM', 'Rx Error Internal', 'Rx Error Missed Start', 'Rx Error Wrong Toggle', 'Rx Error Short Frame', 'Rx Error Bad CRC', 'Rx Ign Wrong Address', 'Rx Ign Not Wanted',  'Rx Ign Unexpected TID',], expire_time=5.0)
        self.setLayout(layout)

        self.dronecan_stats_group = QGroupBox('DroneCAN Stats', self)
        self.dronecan_stats_layout = QGridLayout()
        self.dronecan_stats_layout.addWidget(self.dronecan_stats_table)
        self.dronecan_stats_group.setLayout(self.dronecan_stats_layout)
        self.dronecan_stats_group.setToolTip('''
DroneCAN Stats shows the statistics of the DroneCAN network.
''')
        self.can_stats_table = table_display.TableDisplay(['Node ID', 'Interface', 'Tx Requests', 'Tx Rejected', 'Tx Overflow', 'Tx Success', 'Tx Timedout', 'Tx Abort', 'Rx Received', 'Rx Overflow', 'Rx Errors', 'Busoff Errors'], expire_time=5.0)

        self.can_stats_group = QGroupBox('CAN Stats', self)
        self.can_stats_layout = QGridLayout()
        self.can_stats_layout.addWidget(self.can_stats_table)
        self.can_stats_group.setLayout(self.can_stats_layout)
        self.can_stats_group.setToolTip('''
CAN Stats shows the statistics of the CAN interface.
''')


        layout.addWidget(self.dronecan_stats_group)
        layout.addWidget(self.can_stats_group)

        self.clear_stats_button = QPushButton('Clear Stats', self)
        self.clear_stats_button.clicked.connect(self.clear_stats)
        layout.addWidget(self.clear_stats_button)

        self.setLayout(layout)
        self.resize(800, 800)
        self.node = node
        self.handlers = [node.add_handler(dronecan.dronecan.protocol.Stats, self.on_dronecan_stats),
                         node.add_handler(dronecan.dronecan.protocol.CanStats, self.on_can_stats)]
        
        self.dronecan_offsets = {}
        self.can_offsets = {}

    def on_dronecan_stats(self, msg):
        '''display dronecan stats'''
        nodeid = msg.transfer.source_node_id
        if nodeid not in self.dronecan_offsets:
            self.dronecan_offsets[nodeid] = [0] * 12
        offsets = self.dronecan_offsets[nodeid]
        self.dronecan_stats_table.update(nodeid, [
            nodeid,
            msg.message.tx_frames - offsets[0],
            msg.message.tx_errors - offsets[1],
            msg.message.rx_frames - offsets[2],
            msg.message.rx_error_oom - offsets[3],
            msg.message.rx_error_internal - offsets[4],
            msg.message.rx_error_missed_start - offsets[5],
            msg.message.rx_error_wrong_toggle - offsets[6],
            msg.message.rx_error_short_frame - offsets[7],
            msg.message.rx_error_bad_crc - offsets[8],
            msg.message.rx_ignored_wrong_address - offsets[9],
            msg.message.rx_ignored_not_wanted - offsets[10],
            msg.message.rx_ignored_unexpected_tid - offsets[11]
        ])

    def on_can_stats(self, msg):
        '''display can stats'''
        nodeid = msg.transfer.source_node_id
        interface = msg.message.interface
        key = (nodeid, interface)
        if key not in self.can_offsets:
            self.can_offsets[key] = [0] * 11
        offsets = self.can_offsets[key]
        self.can_stats_table.update(key, [
            nodeid,
            interface,
            msg.message.tx_requests - offsets[0],
            msg.message.tx_rejected - offsets[1],
            msg.message.tx_overflow - offsets[2],
            msg.message.tx_success - offsets[3],
            msg.message.tx_timedout - offsets[4],
            msg.message.tx_abort - offsets[5],
            msg.message.rx_received - offsets[6],
            msg.message.rx_overflow - offsets[7],
            msg.message.rx_errors - offsets[8],
            msg.message.busoff_errors - offsets[9]
        ])

    def clear_stats(self):
        '''clear all stats and set offsets'''
        for nodeid in self.dronecan_stats_table.data.keys():
            current_values = self.dronecan_stats_table.data[nodeid][1:]
            self.dronecan_offsets[nodeid] = [offset + current for offset, current in zip(self.dronecan_offsets[nodeid], current_values)]

        for key in self.can_stats_table.data.keys():
            current_values = self.can_stats_table.data[key][2:]
            self.can_offsets[key] = [offset + current for offset, current in zip(self.can_offsets[key], current_values)]
        
    def __del__(self):
        for h in self.handlers:
            h.remove()
        global _singleton
        _singleton = None

    def closeEvent(self, event):
        super(StatsPanel, self).closeEvent(event)
        self.__del__()

def spawn(parent, node):
    global _singleton
    if _singleton is None:
        try:
            _singleton = StatsPanel(parent, node)
        except Exception as ex:
            print(ex)

    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()

    return _singleton

get_icon = partial(get_icon, 'fa6s.asterisk')
