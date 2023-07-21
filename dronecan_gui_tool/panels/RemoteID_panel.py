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
    QPlainTextEdit, QPushButton, QLineEdit, QFileDialog, QComboBox, QHBoxLayout
from PyQt5.QtCore import QTimer, Qt
from logging import getLogger
from ..widgets import make_icon_button, get_icon, get_monospace_font, directory_selection
import random
import base64
import struct

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'RemoteID Panel'

logger = getLogger(__name__)

_singleton = None

SECURE_COMMAND_GET_REMOTEID_SESSION_KEY = dronecan.dronecan.remoteid.SecureCommand.Request().SECURE_COMMAND_GET_REMOTEID_SESSION_KEY
SECURE_COMMAND_SET_REMOTEID_CONFIG = dronecan.dronecan.remoteid.SecureCommand.Request().SECURE_COMMAND_SET_REMOTEID_CONFIG

class RemoteIDPanel(QDialog):
    DEFAULT_INTERVAL = 0.1

    def __init__(self, parent, node):
        super(RemoteIDPanel, self).__init__(parent)
        self.setWindowTitle('RemoteID Management Panel')
        self.setAttribute(Qt.WA_DeleteOnClose)              # This is required to stop background timers!

        self.timeout = 5

        self._node = node
        self.session_key = None
        self.sequence = random.randint(0, 0xFFFFFFFF)

        layout = QVBoxLayout()

        self.key_selection = directory_selection.DirectorySelectionWidget(self, 'Secret key file')
        self.command = QLineEdit(self)
        self.send = QPushButton('Send', self)
        self.send.clicked.connect(self.on_send)

        self.node_select = QComboBox()

        self.state = QLineEdit()
        self.state.setText("")
        self.state.setReadOnly(True)

        layout.addLayout(self.labelWidget('Node', self.node_select))
        layout.addWidget(self.key_selection)
        layout.addLayout(self.labelWidget('Command:', self.command))
        layout.addLayout(self.labelWidget('Status:', self.state))
        layout.addWidget(self.send)

        self.setLayout(layout)
        self.resize(400, 200)
        QTimer.singleShot(250, self.update_nodes)


    def labelWidget(self, label, widget):
        '''a widget with a label'''
        hlayout = QHBoxLayout()
        hlayout.addWidget(QLabel(label, self))
        hlayout.addWidget(widget)
        return hlayout

    def on_send(self):
        '''callback for send button'''
        priv_key = self.key_selection.get_selection()
        if priv_key is None:
            self.status_update("Need to select private key")
            return
        self.status_update("Requesting session key")
        self.request_session_key()

    def status_update(self, text):
        '''update status line'''
        self.state.setText(text)

    def update_nodes(self):
        '''update list of available nodes'''
        QTimer.singleShot(250, self.update_nodes)
        from ..widgets.node_monitor import app_node_monitor
        if app_node_monitor is None:
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
                self.node_select.addItem(n)
        
    def get_session_key_response(self, reply):
        '''handle session key response'''
        if not reply:
            self.status_update("timed out")
            return
        self.session_key = bytearray(reply.response.data)
        self.status_update("Got session key")
        self.send_config_change()

    def get_private_key(self):
        '''get private key, return 32 byte key or None'''
        priv_key_file = self.key_selection.get_selection()
        if priv_key_file is None:
            self.status_update("Please select private key file")
            return None
        try:
            d = open(priv_key_file,'r').read()
        except Exception as ex:
            print(ex)
            return None
        ktype = "PRIVATE_KEYV1:"
        if not d.startswith(ktype):
            return None
        return base64.b64decode(d[len(ktype):])
    
    def make_signature(self, seq, command, data):
        '''make a signature'''
        import monocypher
        private_key = self.get_private_key()
        d = struct.pack("<II", seq, command)
        d += data
        if command != SECURE_COMMAND_GET_REMOTEID_SESSION_KEY:
            if self.session_key is None:
                raise Exception("No session key")
            d += self.session_key
        return monocypher.signature_sign(private_key, d)

    def get_target_node(self):
        '''get the target node'''
        return int(self.node_select.currentText().split(':')[0])

    def request_session_key(self):
        '''request a session key'''
        sig = self.make_signature(self.sequence, SECURE_COMMAND_GET_REMOTEID_SESSION_KEY, bytes())
        self._node.request(dronecan.dronecan.remoteid.SecureCommand.Request(
            sequence=self.sequence,
            operation=SECURE_COMMAND_GET_REMOTEID_SESSION_KEY,
            sig_length=len(sig),
            data=sig,
            timeout=self.timeout),
            self.get_target_node(),
            self.get_session_key_response)
        self.sequence = (self.sequence+1) % (1<<32)
        print("Requested session key")

    def config_change_response(self, reply):
        if not reply:
            self.status_update("timed out")
            return
        result_map = {
            0: "ACCEPTED",
            1: "TEMPORARILY_REJECTED",
            2: "DENIED",
            3: "UNSUPPORTED",
            4: "FAILED" }
        result = result_map.get(reply.response.result, "invalid")
        self.status_update("Got change response: %s" % result)

    def send_config_change(self):
        '''send remoteid config change'''
        req = self.command.text().encode('utf-8')
        sig = self.make_signature(self.sequence, SECURE_COMMAND_SET_REMOTEID_CONFIG, req)
        self._node.request(dronecan.dronecan.remoteid.SecureCommand.Request(
            sequence=self.sequence,
            operation=SECURE_COMMAND_SET_REMOTEID_CONFIG,
            sig_length=len(sig),
            data=req+sig,
            timeout=self.timeout),
            self.get_target_node(),
            self.config_change_response)
        self.sequence = (self.sequence+1) % (1<<32)
        self.status_update("Requested config change")

    def __del__(self):
        global _singleton
        _singleton = None

    def closeEvent(self, event):
        global _singleton
        _singleton = None
        super(RemoteIDPanel, self).closeEvent(event)


def spawn(parent, node):
    global _singleton
    if _singleton is None:
        try:
            _singleton = RemoteIDPanel(parent, node)
        except Exception as ex:
            print(ex)

    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()

    return _singleton


get_icon = partial(get_icon, 'asterisk')
