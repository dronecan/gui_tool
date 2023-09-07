#
# Copyright (C) 2023  UAVCAN Development Team  <dronecan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Andrew Tridgell
#

import dronecan
from functools import partial
from PyQt5.QtWidgets import QVBoxLayout, QWidget, QLabel, QDialog, \
    QPlainTextEdit, QPushButton, QLineEdit, QFileDialog, QComboBox, QHBoxLayout, QSpinBox
from PyQt5.QtCore import QTimer, Qt
from logging import getLogger
from ..widgets import make_icon_button, get_icon, get_monospace_font
from ..widgets import table_display
import random
import base64
import struct

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'Hobbywing ESC Panel'

logger = getLogger(__name__)

_singleton = None

class HobbywingPanel(QDialog):
    DEFAULT_INTERVAL = 0.1

    def __init__(self, parent, node):
        super(HobbywingPanel, self).__init__(parent)
        self.setWindowTitle('Hobbywing ESC Panel')
        self.setAttribute(Qt.WA_DeleteOnClose)              # This is required to stop background timers!

        self._node = node

        layout = QVBoxLayout()

        self.table = table_display.TableDisplay(['Node','ThrottleID','RPM','Voltage','Current','Temperature','Direction'])
        layout.addWidget(self.table)

        self.baudrate = QComboBox(self)
        for b in [50000, 100000, 200000, 250000, 500000, 1000000]:
            self.baudrate.addItem(str(b))
        self.baudrate.setCurrentText(str(1000000))
        self.baudrate_set = QPushButton('Set', self)
        self.baudrate_set.clicked.connect(self.on_baudrate_set)
        
        layout.addLayout(self.labelWidget('Baudrate:', [self.baudrate, self.baudrate_set]))

        self.throttleid = QSpinBox(self)
        self.throttleid.setMinimum(1)
        self.throttleid.setMaximum(32)
        self.throttleid.setValue(1)
        self.throttleid_set = QPushButton('Set', self)
        self.throttleid_set.clicked.connect(self.on_throttleid_set)

        layout.addLayout(self.labelWidget('ThrottleID:', [self.throttleid, self.throttleid_set]))

        self.nodeid = QSpinBox(self)
        self.nodeid.setMinimum(1)
        self.nodeid.setMaximum(127)
        self.nodeid.setValue(1)
        self.nodeid_set = QPushButton('Set', self)
        self.nodeid_set.clicked.connect(self.on_nodeid_set)
        
        layout.addLayout(self.labelWidget('NodeID:', [self.nodeid, self.nodeid_set]))

        self.direction = QComboBox(self)
        self.direction.addItem("CW")
        self.direction.addItem("CCW")
        self.direction.setCurrentText("CW")
        self.direction_set = QPushButton('Set', self)
        self.direction_set.clicked.connect(self.on_direction_set)
        
        layout.addLayout(self.labelWidget('Direction:', [self.direction, self.direction_set]))

        self.msg1rate = QComboBox(self)
        for r in [0, 1, 10, 20, 50, 100, 200, 250, 500]:
            self.msg1rate.addItem(str(r))
        self.msg1rate.setCurrentText("50")
        self.msg1rate_set = QPushButton('Set', self)
        self.msg1rate_set.clicked.connect(self.on_msg1rate_set)
        
        layout.addLayout(self.labelWidget('Msg1Rate:', [self.msg1rate, self.msg1rate_set]))

        self.msg2rate = QComboBox(self)
        for r in [0, 1, 10, 20, 50, 100, 200, 250, 500]:
            self.msg2rate.addItem(str(r))
        self.msg2rate.setCurrentText("10")
        self.msg2rate_set = QPushButton('Set', self)
        self.msg2rate_set.clicked.connect(self.on_msg2rate_set)
        
        layout.addLayout(self.labelWidget('Msg2Rate:', [self.msg2rate, self.msg2rate_set]))

        self.msg3rate = QComboBox(self)
        for r in [0, 1, 10, 20, 50, 100, 200, 250, 500]:
            self.msg3rate.addItem(str(r))
        self.msg3rate.setCurrentText("10")
        self.msg3rate_set = QPushButton('Set', self)
        self.msg3rate_set.clicked.connect(self.on_msg3rate_set)
        
        layout.addLayout(self.labelWidget('Msg3Rate:', [self.msg3rate, self.msg3rate_set]))
        
        self.setLayout(layout)
        self.resize(400, 200)

        self.handlers = [node.add_handler(dronecan.com.hobbywing.esc.StatusMsg1, self.handle_StatusMsg1),
                         node.add_handler(dronecan.com.hobbywing.esc.StatusMsg2, self.handle_StatusMsg2),
                         node.add_handler(dronecan.com.hobbywing.esc.GetEscID, self.handle_GetEscID)]

        QTimer.singleShot(500, self.request_ids)


    def handle_reply(self, msg):
        '''handle a reply to a set'''
        if msg is not None:
            print('REPLY: ', dronecan.to_yaml(msg))
        else:
            print("No reply")

    def on_throttleid_set(self):
        '''set throttle ID'''
        nodeid = self.table.get_selected()
        req = dronecan.com.hobbywing.esc.SetID.Request()
        req.node_id = nodeid
        req.throttle_channel = int(self.throttleid.value())
        self._node.request(req, nodeid, self.handle_reply)

    def on_nodeid_set(self):
        '''set node ID'''
        nodeid = self.table.get_selected()
        thr_id = int(self.table.data[nodeid][1])
        req = dronecan.com.hobbywing.esc.SetID.Request()
        req.node_id = int(self.nodeid.value())
        req.throttle_channel = thr_id
        self._node.request(req, nodeid, self.handle_reply)
        
    def on_baudrate_set(self):
        '''set baudrate'''
        nodeid = self.table.get_selected()
        req = dronecan.com.hobbywing.esc.SetBaud.Request()
        bmap = {
            1000000 : req.BAUD_1MBPS,
            500000 : req.BAUD_500KBPS,
            250000 : req.BAUD_250KBPS,
            200000 : req.BAUD_200KBPS,
            100000 : req.BAUD_100KBPS,
            50000 : req.BAUD_50KBPS,
        }
        baudrate = int(self.baudrate.currentText())
        req.baud = bmap[baudrate]
        self._node.request(req, nodeid, self.handle_reply)

    def on_direction_set(self):
        '''set direction'''
        nodeid = self.table.get_selected()
        req = dronecan.com.hobbywing.esc.SetDirection.Request()
        req.direction = 0 if self.direction.currentText() == "CW" else 1
        self._node.request(req, nodeid, self.handle_reply)

    def set_rate(self, nodeid, msgid, rate):
        '''set a message rate'''
        req = dronecan.com.hobbywing.esc.SetReportingFrequency.Request()
        req.option = req.OPTION_WRITE
        req.MSG_ID = msgid
        rmap = {
            500 : req.RATE_500HZ,
            250 : req.RATE_250HZ,
            200 : req.RATE_200HZ,
            100 : req.RATE_100HZ,
            50 : req.RATE_50HZ,
            20 : req.RATE_20HZ,
            10 : req.RATE_10HZ,
            1 : req.RATE_1HZ,
        }
        if not rate in rmap:
            print("Invalid rate %d - must be one of %s" % (rate, ','.join(rmap.keys())))
            return
        req.rate = rmap[rate]
        self._node.request(req, nodeid, self.handle_reply)

    def on_msg1rate_set(self):
        '''set msg1 rate'''
        nodeid = self.table.get_selected()
        self.set_rate(nodeid, 20050, int(self.msg1rate.currentText()))

    def on_msg2rate_set(self):
        '''set msg2 rate'''
        nodeid = self.table.get_selected()
        self.set_rate(nodeid, 20051, int(self.msg1rate.currentText()))

    def on_msg3rate_set(self):
        '''set msg3 rate'''
        nodeid = self.table.get_selected()
        self.set_rate(nodeid, 20052, int(self.msg1rate.currentText()))
        
    def handle_GetEscID(self, msg):
        '''handle GetEscID'''
        nodeid = msg.transfer.source_node_id
        if len(msg.message.payload) != 2:
            return
        data = self.table.get(nodeid)
        if data is None:
            data = [nodeid, 0, 0, 0, 0, 0, 0]
        data[1] = msg.message.payload[1]
        self.table.update(nodeid, data)

    def handle_StatusMsg1(self, msg):
        '''handle StatusMsg1'''
        nodeid = msg.transfer.source_node_id
        data = self.table.get(nodeid)
        if data is None:
            data = [nodeid, 0, 0, 0, 0, 0, 0]
        data[6] = "CCW" if msg.message.status & (1<<14) else "CW"
        data[2] = msg.message.rpm
        self.table.update(nodeid, data)

    def handle_StatusMsg2(self, msg):
        '''handle StatusMsg2'''
        nodeid = msg.transfer.source_node_id
        data = self.table.get(nodeid)
        if data is None:
            data = [nodeid, 0, 0, 0, 0, 0, 0]
        data[3] = "%.2f" % (msg.message.input_voltage*0.1)
        data[4] = "%.2f" % (msg.message.current*0.1)
        data[5] = msg.message.temperature
        self.table.update(nodeid, data)

    def request_ids(self):
        '''call GetEscID'''
        QTimer.singleShot(500, self.request_ids)
        req = dronecan.com.hobbywing.esc.GetEscID()
        req.payload = [0]
        self._node.broadcast(req)
        
    def labelWidget(self, label, widgets):
        '''a widget with a label'''
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel(label, self))
        if not isinstance(widgets, list):
            widgets = [widgets]
        for w in widgets:
            hlayout.addWidget(w)
        return hlayout

    def __del__(self):
        for h in self.handlers:
            h.remove()
        global _singleton
        _singleton = None

    def closeEvent(self, event):
        super(HobbywingPanel, self).closeEvent(event)
        self.__del__()


def spawn(parent, node):
    global _singleton
    if _singleton is None:
        try:
            _singleton = HobbywingPanel(parent, node)
        except Exception as ex:
            print(ex)

    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()

    return _singleton


get_icon = partial(get_icon, 'asterisk')
