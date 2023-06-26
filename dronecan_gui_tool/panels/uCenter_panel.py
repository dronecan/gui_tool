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
     QTableWidget, QVBoxLayout, QGroupBox, QTableWidgetItem, QLineEdit
from PyQt5.QtCore import Qt, QTimer
from ..widgets import get_icon
from . import rtcm3
import time
import socket
import errno

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'uCenter Panel'

_singleton = None

class uCenterPanel(QDialog):
    def __init__(self, parent, node):
        super(uCenterPanel, self).__init__(parent)
        self.setWindowTitle('uCenter forwarding')
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.portnumber = 2001
        self.sock = None
        self.listen_sock = None
        self.addr = None
        self.logfile = None
        self.num_rx_bytes = 0
        self.num_tx_bytes = 0
        self.node = node

        layout = QVBoxLayout()

        self.state = QLineEdit()
        self.state.setText("State: disconnected")
        self.state.setReadOnly(True)
        self.rx_bytes = QLineEdit()
        self.rx_bytes.setText("RX Bytes: 0")
        self.rx_bytes.setReadOnly(True)

        self.tx_bytes = QLineEdit()
        self.tx_bytes.setText("TX Bytes: 0")
        self.tx_bytes.setReadOnly(True)

        layout.addWidget(self.state)
        layout.addWidget(self.rx_bytes)
        layout.addWidget(self.tx_bytes)

        self.setLayout(layout)
        self.resize(400, 200)

        self.restart_listen()
        QTimer.singleShot(10, self.check_connection)
        node.add_handler(dronecan.uavcan.tunnel.Broadcast, self.handle_tunnel_Broadcast)

    def handle_tunnel_Broadcast(self, msg):
        '''forward GPS data to uCenter'''
        if self.sock is not None:
            buf = msg.message.buffer.to_bytes()
            self.sock.send(buf)
            self.num_rx_bytes += len(buf)
            self.rx_bytes.setText("RX Bytes: %u" % self.num_rx_bytes)
            if self.logfile is not None:
                self.logfile.write(buf)
                self.logfile.flush()


    def __del__(self):
        print("uCenter closing")
        if self.listen_sock is not None:
            self.listen_sock.close()
        if self.sock is not None:
            self.sock.close()
        self.node.remove_handlers(dronecan.uavcan.tunnel.Broadcast)
        global _singleton
        _singleton = None

    def closeEvent(self, event):
        self.__del__()
        super(uCenterPanel, self).closeEvent(event)

    def restart_listen(self):
        if self.listen_sock is not None:
            self.listen_sock.close()
        self.listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        self.listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_sock.bind(('', self.portnumber))
        self.listen_sock.setblocking(False)
        self.listen_sock.listen(1)
        self.state.setText("State: disconnected")

    def check_connection(self):
        QTimer.singleShot(10, self.check_connection)
        if self.sock is not None:
            try:
                buf = self.sock.recv(64)
            except socket.error as ex:
                if ex.errno not in [ errno.EAGAIN, errno.EWOULDBLOCK ]:
                    print("Closing: ", ex)
                    self.sock = None
                return
            pkt = dronecan.uavcan.tunnel.Broadcast()
            pkt.protocol.protocol = 2 # GPS
            pkt.channel_id = 1
            pkt.buffer = buf
            self.node.broadcast(pkt)
            self.num_tx_bytes += len(buf)
            self.tx_bytes.setText("TX Bytes: %u" % self.num_tx_bytes)

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
            self.state.setText("State: connection from %s:%u" % (self.addr[0], self.addr[1]))
            self.num_rx_bytes = 0
            self.num_tx_bytes = 0
            print("ucenter connection from %s" % str(self.addr))
            try:
                self.logfile = open("ubx.dat", "wb")
            except Exception:
                pass



def spawn(parent, node):
    global _singleton
    if _singleton is None:
        try:
            _singleton = uCenterPanel(parent, node)
        except Exception as ex:
            print(ex)

    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()

    return _singleton

get_icon = partial(get_icon, 'asterisk')
