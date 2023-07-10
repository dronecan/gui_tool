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
     QVBoxLayout, QGroupBox
from PyQt5.QtCore import Qt, QTimer
from ..widgets import get_icon
from ..widgets import table_display
from . import rtcm3
import time

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'RTK Panel'

_singleton = None

class RTCMData:
    def __init__(self):
        self.last_time = {}
        self.dt = {}
        self.decoder = rtcm3.RTCM3()
        self.table = table_display.TableDisplay(['Node','RTCM_ID','Len','Rate(Hz)'])

    def handle_msg(self, msg):
        nodeid = msg.transfer.source_node_id
        tstamp = msg.transfer.ts_real
        data = msg.message.data.to_bytes()
        for b in data:
            if not self.decoder.read(chr(b)):
                continue
            pkt_id = self.decoder.get_packet_ID()
            pkt_len = len(self.decoder.get_packet())
            key = (pkt_id,pkt_len)
            if not key in self.last_time:
                self.last_time[key] = tstamp

            self.dt[key] = 0.2
            dt = tstamp - self.last_time[key]
            self.last_time[key] = tstamp
            self.dt[key] = 0.9 * self.dt[key] + 0.1 * dt
            rate_str = "%.1f" % (1.0/self.dt[key])

            self.table.update(key, [nodeid, pkt_id, pkt_len, rate_str])


# mapping of Fix2 status, mode and sub_mode to fix string
fix_status = {
    (0,0,0) : "None (0)",
    (1,0,0) : "NoFix (1)",
    (2,0,0) : "2D (2)",
    (3,0,0) : "3D (3)",
    (3,1,1) : "3D SBAS (4)",
    (3,2,0) : "RTK Float (5)",
    (3,2,1) : "RTK Fixed (6)",
}

class RTKPanel(QDialog):
    def __init__(self, parent, node):
        super(RTKPanel, self).__init__(parent)
        self.setWindowTitle('RTK Information Panel')
        self.setAttribute(Qt.WA_DeleteOnClose)              # This is required to stop background timers!

        layout = QVBoxLayout()

        # Fix2 display
        self.fix2_table = table_display.TableDisplay(['Node','Status','NumSats', 'Rate(Hz)'])
        self.fix2_last_time = {}
        self.fix2_dt = {}

        fix2_group = QGroupBox('Fix2 Status', self)
        fix2_layout = QGridLayout()
        fix2_layout.addWidget(self.fix2_table)
        fix2_group.setLayout(fix2_layout)
        fix2_group.setToolTip('''
The Fix2 message give the fix status of each GPS.
For RTK moving baseline the rover should be 'RTK Fixed (6)' when operating correctly.
''')

        # MovingBaseline Display
        self.mb = RTCMData()
        mb_group = QGroupBox('MovingBaseline Data', self)
        mb_layout = QGridLayout()
        mb_layout.addWidget(self.mb.table)
        mb_group.setLayout(mb_layout)
        mb_group.setToolTip('''
The MovingBaseline message provide correction data from a moving baseline base GPS to
a moving baseline rover GPS in order to achieve a relative RTK fix which allows the calculation
of a GPS yaw value
''')

        # RTCM Display
        self.rtcm = RTCMData()
        rtcm_group = QGroupBox('RTCMStream Data', self)
        rtcm_layout = QGridLayout()
        rtcm_layout.addWidget(self.rtcm.table)
        rtcm_group.setLayout(rtcm_layout)
        rtcm_group.setToolTip('''
The RTCMStream message provide correction data from a ground station to a GPS to allow
it to get a global RTK fix.
''')

        self.relpos_table = table_display.TableDisplay(['Node','RelHeading','Dist(m)', 'RelDown(m)'])
        relpos_group = QGroupBox('RelPosHeading Status', self)
        relpos_layout = QGridLayout()
        relpos_layout.addWidget(self.relpos_table)
        relpos_group.setLayout(relpos_layout)
        relpos_group.setToolTip('''
The RelPosHeading message provides information on the relative position of the two GPS modules.
The distance should match the actual distance between the antennas.
''')

        layout.addWidget(fix2_group)
        layout.addWidget(mb_group)
        layout.addWidget(rtcm_group)
        layout.addWidget(relpos_group)
        self.setLayout(layout)
        self.resize(self.minimumWidth(), self.minimumHeight())

        self.handlers = [node.add_handler(dronecan.uavcan.equipment.gnss.Fix2, self.handle_Fix2),
                         node.add_handler(dronecan.ardupilot.gnss.MovingBaselineData, self.handle_RTCM_MovingBase),
                         node.add_handler(dronecan.uavcan.equipment.gnss.RTCMStream, self.handle_RTCM_Stream),
                         node.add_handler(dronecan.ardupilot.gnss.RelPosHeading, self.handle_RelPos)]

    def handle_Fix2(self, msg):
        '''display Fix2 data in table'''
        nodeid = msg.transfer.source_node_id
        tstamp = msg.transfer.ts_real
        if not nodeid in self.fix2_last_time:
            self.fix2_last_time[nodeid] = tstamp
            self.fix2_dt[nodeid] = 0.2
        dt = tstamp - self.fix2_last_time[nodeid]
        self.fix2_dt[nodeid] = 0.9 * self.fix2_dt[nodeid] + 0.1 * dt
        self.fix2_last_time[nodeid] = tstamp

        status_key = (msg.message.status, msg.message.mode, msg.message.sub_mode)
        status_str = fix_status.get(status_key, str(status_key))
        rate_str = "%.1f" % (1.0 / self.fix2_dt[nodeid])
        self.fix2_table.update(nodeid, [nodeid, status_str, msg.message.sats_used, rate_str])
        #print(nodeid, dronecan.to_yaml(msg))

    def handle_RTCM_MovingBase(self, msg):
        '''display RTCM MovingBaseline data in table'''
        self.mb.handle_msg(msg)

    def handle_RTCM_Stream(self, msg):
        '''display RTCMStream data in table'''
        self.rtcm.handle_msg(msg)

    def handle_RelPos(self, msg):
        '''display RelPos data in table'''
        nodeid = msg.transfer.source_node_id
        self.relpos_table.update(nodeid, [nodeid,
                                          "%.1f" % msg.message.reported_heading_deg,
                                          "%.2f" % msg.message.relative_distance_m,
                                          "%.2f" % msg.message.relative_down_pos_m])

        
    def __del__(self):
        for h in self.handlers:
            h.remove()
        global _singleton
        _singleton = None

    def closeEvent(self, event):
        super(RTKPanel, self).closeEvent(event)
        self.__del__()

def spawn(parent, node):
    global _singleton
    if _singleton is None:
        try:
            _singleton = RTKPanel(parent, node)
        except Exception as ex:
            print(ex)

    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()

    return _singleton

get_icon = partial(get_icon, 'asterisk')
