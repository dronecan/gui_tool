#
# Copyright (C) 2023 DroneCAN Development Team <dronecan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Andrew Tridgell
#

import dronecan
from functools import partial
from PyQt5.QtWidgets import QGridLayout, QWidget, QLabel, QDialog, \
     QTableWidget, QVBoxLayout, QGroupBox, QTableWidgetItem, QLineEdit, \
     QComboBox, QHBoxLayout, QSpinBox
from PyQt5.QtCore import Qt, QTimer
from ..widgets import get_icon
from . import rtcm3
import time
import socket
import errno

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'Serial Forwarding'

_singleton = None

class serialPanel(QDialog):
    def __init__(self, parent, node):
        super(serialPanel, self).__init__(parent)
        self.setWindowTitle('Serial Forwarding')
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.sock = None
        self.listen_sock = None
        self.addr = None
        self.num_rx_bytes = 0
        self.num_tx_bytes = 0
        self.node = node
        self.tunnel = None
        self.target_dev = -1

        layout = QVBoxLayout()

        self.node_select = QComboBox()
        self.baud_select = QComboBox()
        for b in ["Unchanged", 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]:
            self.baud_select.addItem(str(b))
        self.baud_select.currentIndexChanged.connect(self.change_baud)

        self.lock_select = QComboBox()
        self.lock_select.addItem("UnLocked")
        self.lock_select.addItem("Locked")
        self.lock_select.currentIndexChanged.connect(self.update_locked)

        self.port_select = QSpinBox()
        self.port_select.setMinimum(1)
        self.port_select.setMaximum(65535)
        self.port_select.setValue(2001)
        self.port_select.valueChanged.connect(self.restart_listen)

        self.state = QLineEdit()
        self.state.setText("disconnected")
        self.state.setReadOnly(True)
        self.rx_bytes = QLineEdit()
        self.rx_bytes.setText("0")
        self.rx_bytes.setReadOnly(True)

        self.tx_bytes = QLineEdit()
        self.tx_bytes.setText("0")
        self.tx_bytes.setReadOnly(True)

        layout.addLayout(self.labelWidget('Node', self.node_select))
        layout.addLayout(self.labelWidget('UART Locking', self.lock_select))
        layout.addLayout(self.labelWidget('Baudrate', self.baud_select))
        layout.addLayout(self.labelWidget('Listen Port', self.port_select))
        layout.addLayout(self.labelWidget("State", self.state))
        layout.addLayout(self.labelWidget("RX Bytes", self.rx_bytes))
        layout.addLayout(self.labelWidget("TX Bytes", self.tx_bytes))

        self.setLayout(layout)
        self.resize(400, 200)

        self.restart_listen()
        QTimer.singleShot(10, self.check_connection)
        QTimer.singleShot(250, self.update_nodes)

    def labelWidget(self, label, widget):
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel(label, self))
        hlayout.addWidget(widget)
        return hlayout
        
    def __del__(self):
        print("serial closing")
        if self.listen_sock is not None:
            self.listen_sock.close()
        if self.sock is not None:
            self.sock.close()
        if self.tunnel is not None:
            self.tunnel.close()
            self.tunnel = None
        global _singleton
        _singleton = None

    def closeEvent(self, event):
        self.__del__()
        super(serialPanel, self).closeEvent(event)

    def update_nodes(self):
        '''update list of available nodes'''
        QTimer.singleShot(250, self.update_nodes)
        from ..widgets.node_monitor import app_node_monitor
        if app_node_monitor is None:
            print("no app_node_monitor")
            return
        node_list = []
        for nid in app_node_monitor._registry.keys():
            r = app_node_monitor._registry[nid]
            if r.info is not None:
                node_list.append("%u: %s" % (nid, r.info.name.decode()))
            else:
                node_list.append("%u" % nid)
        node_list = sorted(node_list)
        current_node = sorted([self.node_select.itemText(i) for i in range(self.node_select.count())])
        for n in node_list:
            if not n in current_node:
                print("Adding %s" % n)
                self.node_select.addItem(n)

    def restart_listen(self):
        '''stop and restart listening socket'''
        if self.listen_sock is not None:
            self.listen_sock.close()
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_sock.bind(('', int(self.port_select.value())))
        self.listen_sock.setblocking(False)
        self.listen_sock.listen(1)
        self.state.setText("disconnected")

    def get_baudrate(self):
        '''work out baud rate to use'''
        baud = self.baud_select.currentText()
        return 0 if baud == "Unchanged" else int(baud)
        
    def change_baud(self):
        '''callback when selected baud rate changes'''
        if self.tunnel:
            baud = self.get_baudrate()
            self.tunnel.baudrate = baud
            print("change baudrate to %u" % baud)

    def update_locked(self):
        '''callback when locked state changes'''
        if self.tunnel:
            locked = self.lock_select.currentText() == "Locked"
            self.tunnel.lock_port = locked

    def process_socket(self):
        '''process data from the socket'''
        while True:
            try:
                buf = self.sock.recv(120)
            except socket.error as ex:
                if ex.errno not in [ errno.EAGAIN, errno.EWOULDBLOCK ]:
                    print("Closing: ", ex)
                    self.sock = None
                    if self.tunnel is not None:
                        self.tunnel.close()
                        self.tunnel = None
                return
            if buf is None or len(buf) == 0:
                break
            self.tunnel.write(buf)
            self.num_tx_bytes += len(buf)
            self.tx_bytes.setText("%u" % self.num_tx_bytes)

    def process_tunnel(self):
        '''process data from the tunnel'''
        while True:
            buf = self.tunnel.read(120)
            if buf is None or len(buf) == 0:
                break
            try:
                self.sock.send(buf)
            except Exception as ex:
                print("Closing: ", ex)
                self.sock = None
                if self.tunnel is not None:
                    self.tunnel.close()
                    self.tunnel = None
                return

            self.num_rx_bytes += len(buf)
            self.rx_bytes.setText("%u" % self.num_rx_bytes)
            
    def check_connection(self):
        '''called at 100Hz to process data'''
        QTimer.singleShot(10, self.check_connection)
        if self.sock is not None:
            self.process_socket()
            self.process_tunnel()

        if self.sock is None:
            try:
                sock, self.addr = self.listen_sock.accept()
            except Exception as e:
                if e.errno not in [ errno.EAGAIN, errno.EWOULDBLOCK ]:
                    print("ucenter listen fail")
                    self.restart_listen()
                    return
                return
            self.sock = sock
            self.sock.setblocking(False)
            self.state.setText("connection from %s:%u" % (self.addr[0], self.addr[1]))
            self.num_rx_bytes = 0
            self.num_tx_bytes = 0
            if self.tunnel is not None:
                self.tunnel.close()
            target_node = int(self.node_select.currentText().split(':')[0])

            locked = self.lock_select.currentText() == "Locked"
            self.tunnel = dronecan.DroneCANSerial(None, target_node, self.target_dev,
                                                  node=self.node,
                                                  lock_port=locked, baudrate=self.get_baudrate())
            print("ucenter connection from %s" % str(self.addr))


def spawn(parent, node):
    global _singleton
    if _singleton is None:
        try:
            _singleton = serialPanel(parent, node)
        except Exception as ex:
            print(ex)

    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()

    return _singleton

get_icon = partial(get_icon, 'asterisk')
