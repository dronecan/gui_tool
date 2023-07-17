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
     QComboBox, QHBoxLayout, QSpinBox, QCheckBox
from PyQt5.QtCore import Qt, QTimer
from ..widgets import get_icon
from . import rtcm3
import time
import socket
import errno
import struct

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'Serial Forwarding'

_singleton = None

# protocol constants
PREAMBLE1 = 0xb5
PREAMBLE2 = 0x62

CLASS_ACK = 0x05
CLASS_CFG = 0x06

MSG_CFG_PRT = 0x00

MSG_ACK_NACK = 0x00
MSG_ACK_ACK = 0x01

class UBloxError(Exception):
    '''Ublox error class'''
    def __init__(self, msg):
        Exception.__init__(self, msg)
        self.message = msg

class UBloxDescriptor:
    '''class used to describe the layout of a UBlox message'''
    def __init__(self, name, msg_format, fields=[], count_field=None, format2=None, fields2=None):
        self.name = name
        self.msg_format = msg_format
        self.fields = fields
        self.count_field = count_field
        self.format2 = format2
        self.fields2 = fields2

    def ArrayParse(self, field):
        '''parse an array descriptor'''
        arridx = field.find('[')
        if arridx == -1:
            return (field, -1)
        alen = int(field[arridx+1:-1])
        fieldname = field[:arridx]
        return (fieldname, alen)
        
    def unpack(self, msg):
        '''unpack a UBloxMessage, creating the .fields and ._recs attributes in msg'''
        msg._fields = {}

        # unpack main message blocks. A comm
        formats = self.msg_format.split(',')
        buf = msg._buf[6:-2]
        count = 0
        msg._recs = []
        fields = self.fields[:]
        for fmt in formats:
            size1 = struct.calcsize(fmt)
            if size1 > len(buf):
                raise UBloxError("%s INVALID_SIZE1: %u>%u fmt='%s'" % (self.name, size1, len(buf), fmt))
            f1 = list(struct.unpack(fmt, buf[:size1]))
            i = 0
            while i < len(f1):
                field = fields.pop(0)
                (fieldname, alen) = self.ArrayParse(field)
                if alen == -1:
                    msg._fields[fieldname] = f1[i]
                    if self.count_field == fieldname:
                        count = int(f1[i])
                    i += 1
                else:
                    msg._fields[fieldname] = [0]*alen
                    for a in range(alen):
                        msg._fields[fieldname][a] = f1[i]
                        i += 1
            buf = buf[size1:]
            if len(buf) == 0:
                break

        if self.count_field == '_remaining':
            count = len(buf) / struct.calcsize(self.format2)

        if count == 0:
            msg._unpacked = True
            #if len(buf) != 0:
            #    raise UBloxError("EXTRA_BYTES=%u" % len(buf))
            return

        size2 = struct.calcsize(self.format2)
        for c in range(count):
            r = UBloxAttrDict()
            if size2 > len(buf):
                raise UBloxError("INVALID_SIZE=%u, " % len(buf))
            f2 = list(struct.unpack(self.format2, buf[:size2]))
            for i in range(len(self.fields2)):
                r[self.fields2[i]] = f2[i]
            buf = buf[size2:]
            msg._recs.append(r)
        if len(buf) != 0:
            raise UBloxError("EXTRA_BYTES=%u" % len(buf))
        msg._unpacked = True

    def pack(self, msg, msg_class=None, msg_id=None):
        '''pack a UBloxMessage from the .fields and ._recs attributes in msg'''
        f1 = []
        if msg_class is None:
            msg_class = msg.msg_class()
        if msg_id is None:
            msg_id = msg.msg_id()
        msg._buf = ''

        fields = self.fields[:]
        for f in fields:
            (fieldname, alen) = self.ArrayParse(f)
            if not fieldname in msg._fields:
                break
            if alen == -1:
                f1.append(msg._fields[fieldname])
            else:
                for a in range(alen):
                    f1.append(msg._fields[fieldname][a])                    
        try:
            # try full length message
            fmt = self.msg_format.replace(',', '')
            msg._buf = struct.pack(fmt, *tuple(f1))
        except Exception as e:
            # try without optional part
            fmt = self.msg_format.split(',')[0]
            msg._buf = struct.pack(fmt, *tuple(f1))

        length = len(msg._buf)
        if msg._recs:
            length += len(msg._recs) * struct.calcsize(self.format2)
        header = struct.pack('<BBBBH', PREAMBLE1, PREAMBLE2, msg_class, msg_id, length)
        msg._buf = header + msg._buf

        for r in msg._recs:
            f2 = []
            for f in self.fields2:
                f2.append(r[f])
            msg._buf += struct.pack(self.format2, *tuple(f2))            
        msg._buf += struct.pack('<BB', *msg.checksum(data=msg._buf[2:]))

    def format(self, msg):
        '''return a formatted string for a message'''
        if not msg._unpacked:
            self.unpack(msg)
        ret = self.name + ': '
        for f in self.fields:
            (fieldname, alen) = self.ArrayParse(f)
            if not fieldname in msg._fields:
                continue
            v = msg._fields[fieldname]
            if isinstance(v, list):
                ret += '%s=[' % fieldname
                for a in range(alen):
                    ret += '%s, ' % v[a]
                ret = ret[:-2] + '], '
            elif isinstance(v, str):
                ret += '%s="%s", ' % (f, v.rstrip(' \0'))
            else:
                ret += '%s=%s, ' % (f, v)
        for r in msg._recs:
            ret += '[ '
            for f in self.fields2:
                v = r[f]
                ret += '%s=%s, ' % (f, v)
            ret = ret[:-2] + ' ], '
        return ret[:-2]

class UBloxMessage:
    '''UBlox message class - holds a UBX binary message'''
    def __init__(self, msg_class=None, msg_id=None, payload=None):
        self._buf = bytearray()
        self._fields = {}
        self._recs = []
        self._unpacked = False
        self.debug_level = 0
        if msg_class is not None and msg_id is not None and payload is not None:
            self.pack_message(msg_class, msg_id, payload)

    def __str__(self):
        '''format a message as a string'''
        return self.name()

    def __getattr__(self, name):
        '''allow access to message fields'''
        try:
            return self._fields[name]
        except KeyError:
            if name == 'recs':
                return self._recs
            raise AttributeError(name)

    def __setattr__(self, name, value):
        '''allow access to message fields'''
        if name.startswith('_'):
            self.__dict__[name] = value
        else:
            self._fields[name] = value

    def have_field(self, name):
        '''return True if a message contains the given field'''
        return name in self._fields

    def debug(self, level, msg):
        '''write a debug message'''
        if self.debug_level >= level:
            print(msg)

    def name(self):
        '''return the short string name for a message'''
        return "UBX(0x%02x,0x%02x,len=%u)" % (self.msg_class(), self.msg_id(), self.msg_length())

    def msg_class(self):
        '''return the message class'''
        return self._buf[2]

    def msg_id(self):
        '''return the message id within the class'''
        return self._buf[3]

    def msg_type(self):
        '''return the message type tuple (class, id)'''
        return (self.msg_class(), self.msg_id())

    def msg_length(self):
        '''return the payload length'''
        (payload_length,) = struct.unpack('<H', self._buf[4:6])
        return payload_length

    def valid_so_far(self):
        '''check if the message is valid so far'''
        if len(self._buf) > 0 and self._buf[0] != PREAMBLE1:
            return False
        if len(self._buf) > 1 and self._buf[1] != PREAMBLE2:
            return False
        needed = self.needed_bytes()
        if needed > 1000:
            return False
        if needed == 0 and not self.valid():
            return False
        return True

    def add(self, buf):
        '''add some bytes to a message'''
        self._buf += buf
        while not self.valid_so_far() and len(self._buf) > 0:
            '''handle corrupted streams'''
            self._buf = self._buf[1:]
        if self.needed_bytes() < 0:
            self._buf = bytearray()

    def checksum(self, data=None):
        '''return a checksum tuple for a message'''
        if data is None:
            data = self._buf[2:-2]
        cs = 0
        ck_a = 0
        ck_b = 0
        for i in data:
            ck_a = (ck_a + i) & 0xFF
            ck_b = (ck_b + ck_a) & 0xFF
        return (ck_a, ck_b)

    def valid_checksum(self):
        '''check if the checksum is OK'''
        (ck_a, ck_b) = self.checksum()
        d = self._buf[2:-2]
        (ck_a2, ck_b2) = struct.unpack('<BB', self._buf[-2:])
        return ck_a == ck_a2 and ck_b == ck_b2

    def needed_bytes(self):
        '''return number of bytes still needed'''
        if len(self._buf) < 6:
            return 8 - len(self._buf)
        return self.msg_length() + 8 - len(self._buf)

    def valid(self):
        '''check if a message is valid'''
        return len(self._buf) >= 8 and self.needed_bytes() == 0 and self.valid_checksum()

    def raw(self):
        '''return the raw bytes'''
        return self._buf

    def pack_message(self, msg_class, msg_id, payload):
        self._buf = struct.pack('<BBBBH', PREAMBLE1, PREAMBLE2, msg_class, msg_id, len(payload))
        self._buf += payload
        (ck_a, ck_b) = self.checksum(self._buf[2:])
        self._buf += struct.pack('<BB', ck_a, ck_b)

# list of supported message types.
msg_types = {
    (CLASS_CFG, MSG_CFG_PRT)    : UBloxDescriptor('CFG_PRT',
                                                  '<B,<BHIIHHHH',
                                                  ['portID', 'reserved0', 'txReady', 'mode', 'baudRate', 'inProtoMask', 
                                                   'outProtoMask', 'reserved4', 'reserved5']),
    (CLASS_ACK, MSG_ACK_ACK)    : UBloxDescriptor('ACK_ACK',
                                                  '<BB', 
                                                  ['clsID', 'msgID']),
    (CLASS_ACK, MSG_ACK_NACK)   : UBloxDescriptor('ACK_NACK',
                                                  '<BB', 
                                                  ['clsID', 'msgID']),
}
    

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
        self.ublox_msg_in = None
        self.ublox_msg_out = None

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

        self.ublox_handling = QCheckBox(self)

        layout.addLayout(self.labelWidget('Node', self.node_select))
        layout.addLayout(self.labelWidget('UART Locking', self.lock_select))
        layout.addLayout(self.labelWidget('Baudrate', self.baud_select))
        layout.addLayout(self.labelWidget('Listen Port', self.port_select))
        layout.addLayout(self.labelWidget("State", self.state))
        layout.addLayout(self.labelWidget("RX Bytes", self.rx_bytes))
        layout.addLayout(self.labelWidget("TX Bytes", self.tx_bytes))
        layout.addLayout(self.labelWidget("uBlox message handling", self.ublox_handling))

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
            print("change baudrate to %u" % baud)
            self.tunnel.baudrate = baud

    def update_locked(self):
        '''callback when locked state changes'''
        if self.tunnel:
            locked = self.lock_select.currentText() == "Locked"
            self.tunnel.lock_port = locked

    def send_ublox_baud(self, send_baud, config_baud, port=1, inMask=3, outMask=3, mode=2240):
        '''send a CFG_PRT to set baudrate'''
        save_baud = self.tunnel.baudrate
        payload = struct.pack('<BBHIIHHHH', port, 0xff, 0, mode, config_baud, inMask, outMask, 0xFFFF, 0xFFFF)
        msg = UBloxMessage(msg_class=CLASS_CFG, msg_id=MSG_CFG_PRT, payload=payload)
        desc = msg_types[(CLASS_CFG,MSG_CFG_PRT)]
        desc.unpack(msg)
        self.tunnel.baudrate = send_baud
        self.tunnel.write(msg.raw())
        self.tunnel.baudrate = save_baud

    def handle_ublox_message_out(self):
        '''print uBlox messages going from device to uCenter'''
        mtype = self.ublox_msg_out.msg_type()
        if mtype in msg_types:
            try:
                msg_types[mtype].unpack(self.ublox_msg_out)
                print(">> " + msg_types[mtype].format(self.ublox_msg_out))
                return
            except Exception as ex:
                print(ex)
                pass
        print(">> " + self.ublox_msg_out.name())

    def handle_ublox_data_out(self, buf):
        '''handle ublox data from the GPS'''
        if not self.ublox_handling.checkState():
            self.ublox_msg_out = None
            return
        if self.ublox_msg_out is None:
            self.ublox_msg_out = UBloxMessage()
        while len(buf) > 0:
            needed = self.ublox_msg_out.needed_bytes()
            n = min(needed, len(buf))
            self.ublox_msg_out.add(buf[:n])
            buf = buf[n:]
            if self.ublox_msg_out.valid():
                self.handle_ublox_message_out()
                self.ublox_msg_out = UBloxMessage()

    def delay(self, delay_s):
        t0 = time.time()
        while time.time() - t0 < delay_s:
            # keep the link alive
            self.tunnel.send_bytes(bytearray())
            time.sleep(0.01)

    def handle_ublox_message_in(self):
        '''handle a uBlox message from uCenter'''
        mbuf = self.ublox_msg_in.raw()
        mlen = len(mbuf)

        # avoid flooding the serial port by sleeping for a bit if we are
        # getting data from uCenter faster than the serial port can handle it
        port_rate = self.tunnel.baudrate / 10.0
        delay_needed = mlen / port_rate
        self.delay(delay_needed)

        # write message to the tunnel
        self.tunnel.write(mbuf)

        # interpret the message to see if we should change baudrate
        mtype = self.ublox_msg_in.msg_type()
        if mtype in msg_types:
            try:
                msg_types[mtype].unpack(self.ublox_msg_in)
                print("<< " + msg_types[mtype].format(self.ublox_msg_in))
                if mtype == (CLASS_CFG,MSG_CFG_PRT) and hasattr(self.ublox_msg_in,'baudRate'):
                    self.tunnel.baudrate = self.ublox_msg_in.baudRate
                    self.baud_select.setCurrentText("%u" % self.ublox_msg_in.baudRate)
                    print("uBlox changed baudrate to %u" % self.ublox_msg_in.baudRate)
                return
            except Exception as ex:
                print(ex)
                pass
        print("<< " + self.ublox_msg_in.name())

    def handle_ublox_data_in(self, buf):
        '''handle ublox data from uCenter'''
        if self.ublox_msg_in is None:
            self.ublox_msg_in = UBloxMessage()
        while len(buf) > 0:
            needed = self.ublox_msg_in.needed_bytes()
            n = min(needed, len(buf))
            self.ublox_msg_in.add(buf[:n])
            buf = buf[n:]
            if self.ublox_msg_in.valid():
                self.handle_ublox_message_in()
                self.ublox_msg_in = UBloxMessage()
                
    def process_socket(self):
        '''process data from the socket'''
        while True:
            try:
                buf = self.sock.recv(120)
            except socket.error as ex:
                if ex.errno not in [ errno.EAGAIN, errno.EWOULDBLOCK ]:
                    self.close_socket()
                return
            except Exception:
                self.close_socket()
                return

            if buf is None or len(buf) == 0:
                break
            if self.ublox_handling.checkState():
                # we will send the data on packet boundaries
                self.handle_ublox_data_in(buf)
            else:
                self.ublox_msg_in = None
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
                self.handle_ublox_data_out(buf)
            except Exception:
                self.close_socket()
                return

            self.num_rx_bytes += len(buf)
            self.rx_bytes.setText("%u" % self.num_rx_bytes)

    def close_socket(self):
        '''close the socket on errors'''
        print("Closing socket")
        self.state.setText("disconnected")
        if self.sock is not None:
            self.sock.close()
            self.sock = None
        if self.tunnel is not None:
            self.tunnel.close()
            self.tunnel = None
            
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
