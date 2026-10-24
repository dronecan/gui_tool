#
# Copyright (C) 2016  UAVCAN Development Team  <uavcan.org>
#
# This software is distributed under the terms of the MIT License.
#

"""
Writes CAN frames into a pcapng file that can be opened with Wireshark and other packet analysis tools.
Frames are stored in the Linux SocketCAN format (LINKTYPE_CAN_SOCKETCAN), and the direction of each frame
(received or transmitted) is recorded in the packet flags.
References:
    https://www.ietf.org/archive/id/draft-ietf-opsawg-pcapng-02.html
    https://www.tcpdump.org/linktypes/LINKTYPE_CAN_SOCKETCAN.html
"""

import struct

LINKTYPE_CAN_SOCKETCAN = 227

_BLOCK_TYPE_SECTION_HEADER = 0x0A0D0D0A
_BLOCK_TYPE_INTERFACE_DESCRIPTION = 0x00000001
_BLOCK_TYPE_ENHANCED_PACKET = 0x00000006
_BYTE_ORDER_MAGIC = 0x1A2B3C4D

_OPT_END_OF_OPTIONS = 0
_OPT_SHB_USER_APPLICATION = 4
_OPT_IF_NAME = 2
_OPT_IF_TSRESOL = 9
_OPT_EPB_FLAGS = 2

_EPB_FLAGS_INBOUND = 0b01
_EPB_FLAGS_OUTBOUND = 0b10

_CAN_EFF_FLAG = 0x80000000
_CANFD_FDF = 0x04       # Marks a CAN FD frame in the SocketCAN header

_CAN_MAX_DATA_LENGTH = 8
_CANFD_MAX_DATA_LENGTH = 64


def _pad4(data):
    return data + b'\x00' * (-len(data) % 4)


def _option(code, value):
    return struct.pack('<HH', code, len(value)) + _pad4(value)


def _options(*options):
    return b''.join(options) + struct.pack('<HH', _OPT_END_OF_OPTIONS, 0)


def _block(block_type, body):
    total_length = 12 + len(body)
    return struct.pack('<II', block_type, total_length) + body + struct.pack('<I', total_length)


def make_socketcan_packet(frame):
    """Encodes the frame as a SocketCAN can_frame or canfd_frame; the header is in network byte order."""
    can_id = frame.id | (_CAN_EFF_FLAG if frame.extended else 0)
    data = bytes(frame.data)
    if frame.canfd:
        header = struct.pack('>IBBBB', can_id, len(data), _CANFD_FDF, 0, 0)
        return header + data.ljust(_CANFD_MAX_DATA_LENGTH, b'\x00')
    else:
        header = struct.pack('>IBBBB', can_id, len(data), 0, 0, 0)
        return header + data.ljust(_CAN_MAX_DATA_LENGTH, b'\x00')


class PcapngCANWriter:
    def __init__(self, path, iface_name=None, application_name='DroneCAN GUI Tool'):
        self.path = path
        self.frame_count = 0
        self._file = open(path, 'wb')
        try:
            self._write_header(iface_name, application_name)
        except Exception:
            self._file.close()
            raise

    def _write_header(self, iface_name, application_name):
        shb_body = struct.pack('<IHHq', _BYTE_ORDER_MAGIC, 1, 0, -1)    # Version 1.0, unspecified section length
        shb_body += _options(_option(_OPT_SHB_USER_APPLICATION, application_name.encode('utf8')))
        self._file.write(_block(_BLOCK_TYPE_SECTION_HEADER, shb_body))

        idb_options = [_option(_OPT_IF_TSRESOL, bytes([6]))]           # Timestamps are in microseconds
        if iface_name:
            idb_options.insert(0, _option(_OPT_IF_NAME, iface_name.encode('utf8')))
        idb_body = struct.pack('<HHI', LINKTYPE_CAN_SOCKETCAN, 0, 0)     # No snapshot length limit
        idb_body += _options(*idb_options)
        self._file.write(_block(_BLOCK_TYPE_INTERFACE_DESCRIPTION, idb_body))

    def write_frame(self, direction, frame):
        """
        Args:
            direction:  'rx' or 'tx'
            frame:      An object with the attributes of dronecan.driver.CANFrame
        """
        packet = make_socketcan_packet(frame)
        ts = int(round(frame.ts_real * 1e6))
        flags = _EPB_FLAGS_OUTBOUND if direction == 'tx' else _EPB_FLAGS_INBOUND
        body = struct.pack('<IIIII', 0, ts >> 32, ts & 0xFFFFFFFF, len(packet), len(packet))
        body += _pad4(packet)
        body += _options(_option(_OPT_EPB_FLAGS, struct.pack('<I', flags)))
        self._file.write(_block(_BLOCK_TYPE_ENHANCED_PACKET, body))
        self.frame_count += 1

    def flush(self):
        self._file.flush()

    def close(self):
        self._file.close()
