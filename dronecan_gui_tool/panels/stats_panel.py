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
     QVBoxLayout, QGroupBox, QLineEdit
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
        self.setLayout(layout)
        self.resize(800, 800)
        self.node = node
        self.handlers = [node.add_handler(dronecan.dronecan.protocol.Stats, self.on_dronecan_stats),
                         node.add_handler(dronecan.dronecan.protocol.CanStats, self.on_can_stats)]

    def on_dronecan_stats(self, msg):
        '''display dronecan stats'''
        nodeid = msg.transfer.source_node_id
        self.dronecan_stats_table.update(nodeid, [nodeid, msg.message.tx_frames, msg.message.tx_errors, msg.message.rx_frames, msg.message.rx_error_oom, msg.message.rx_error_internal, msg.message.rx_error_missed_start, msg.message.rx_error_wrong_toggle, msg.message.rx_error_short_frame, msg.message.rx_error_bad_crc, msg.message.rx_ignored_wrong_address, msg.message.rx_ignored_not_wanted, msg.message.rx_ignored_unexpected_tid])

    def on_can_stats(self, msg):
        '''display can stats'''
        nodeid = msg.transfer.source_node_id
        self.can_stats_table.update((nodeid,msg.message.interface), [nodeid, msg.message.interface, msg.message.tx_requests, msg.message.tx_rejected, msg.message.tx_overflow, msg.message.tx_success, msg.message.tx_timedout, msg.message.tx_abort, msg.message.rx_received, msg.message.rx_overflow, msg.message.rx_errors, msg.message.busoff_errors])

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

get_icon = partial(get_icon, 'asterisk')
