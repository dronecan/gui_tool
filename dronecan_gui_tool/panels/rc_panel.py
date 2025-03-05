#
# Copyright (C) 2023 DroneCAN Development Team <dronecan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Huibean Luo <huibean.luo@vimdrones.com>
#

import dronecan
from functools import partial
from PyQt5.QtWidgets import QWidget, QLabel, QDialog, \
     QVBoxLayout, QHBoxLayout, QSlider, QSpinBox, QPushButton
from PyQt5.QtGui import QPainter, QPen, QColor, QFont 
from PyQt5.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt5 import sip
from ..widgets import get_icon

__all__ = 'PANEL_NAME', 'spawn', 'get_icon'

PANEL_NAME = 'RC Panel'

_singleton = None

STATUS_QUALITY_VALID = 1
STATUS_FAILSAFE = 2

DRONECAN_MAX_RC_CHANNELS = 32
DEFAULT_DISPLAY_CHANNELS = 16 
CHANNEL_CENTER_VALUE = 1500
CHANNEL_VALUE_DISPLAY_RANGE_MAX = 2050
CHANNEL_VALUE_DISPLAY_RANGE_MIN = 950 
CHANNEL_VALUE_DISPLAY_RANGE = CHANNEL_VALUE_DISPLAY_RANGE_MAX - CHANNEL_VALUE_DISPLAY_RANGE_MIN

class ChannelSlider(QSlider):
    def __init__(self):
        super(ChannelSlider, self).__init__(Qt.Vertical)

        self.setMinimum(CHANNEL_VALUE_DISPLAY_RANGE_MIN)
        self.setMaximum(CHANNEL_VALUE_DISPLAY_RANGE_MAX)

        self.min_value = CHANNEL_CENTER_VALUE 
        self.max_value = CHANNEL_CENTER_VALUE
        self.valid = False
        self.updateStyleSheet()

    def updateStyleSheet(self):
        if self.valid:
            self.setStyleSheet("""
                QSlider::groove:vertical {
                    border: 0px solid #999999;
                    width: 8px;
                    background: white;
                    margin: 0 2px;
                }
            """)
        else:
            self.setStyleSheet("""
                QSlider::groove:vertical {
                    border: 0px solid #999999;
                    width: 8px;
                    background: gray;
                    margin: 0 2px;
                }
            """)

    def setValid(self, valid):
        self.valid = valid
        self.updateStyleSheet()

    def setValue(self, value):
        super().setValue(value)
        self.min_value = min(self.min_value, value)
        self.max_value = max(self.max_value, value)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)

        painter.setBrush(QColor(0, 255, 0))
        rect_y0 = self.height() * 0.5
        display_value = self.value()
        offset = self.height() * 0.5 * (CHANNEL_CENTER_VALUE - display_value) / (CHANNEL_VALUE_DISPLAY_RANGE * 0.5)
        rect = QRectF(0, rect_y0, self.width(), offset)
        painter.drawRect(rect)

        painter.setPen(Qt.gray)
        painter.drawLine(QPointF(0, self.height() *0.5), QPointF(self.width(), self.height() *0.5))

        if self.min_value != CHANNEL_CENTER_VALUE:
            painter.setPen(Qt.red)
            min_pos = self.height() - abs(self.min_value - CHANNEL_VALUE_DISPLAY_RANGE_MIN) / CHANNEL_VALUE_DISPLAY_RANGE * self.height() 
            painter.drawLine(QPointF(0, min_pos), QPointF(self.width(), min_pos))
        
        if self.max_value != CHANNEL_CENTER_VALUE:
            painter.setPen(Qt.red)
            max_pos = abs(self.max_value - CHANNEL_VALUE_DISPLAY_RANGE_MAX) / CHANNEL_VALUE_DISPLAY_RANGE * self.height() 
            painter.drawLine(QPointF(0, max_pos), QPointF(self.width(), max_pos))

class ChannelSliderItem(QWidget):
    def __init__(self, ch, parent=None):
        super(ChannelSliderItem, self).__init__(parent)

        layout = QVBoxLayout()

        self.ch = ch
        self.slider = ChannelSlider()
        self.slider.setEnabled(False)
        self.slider.setMinimumHeight(60)

        font = QFont()
        font.setPointSize(8) 

        mini_font = QFont()  
        mini_font.setPointSize(6)

        self.channel_value_label = QLabel()
        self.channel_value_label.setFont(font) 

        self.channel_max_value_label = QLabel()
        self.channel_max_value_label.setFont(mini_font)

        self.channel_min_value_label = QLabel()
        self.channel_min_value_label.setFont(mini_font)

        ch_label = QLabel(f'CH{ch}')
        ch_label.setFont(font) 


        layout.addWidget(self.channel_max_value_label)
        layout.setAlignment(self.channel_max_value_label, Qt.AlignCenter)

        layout.addWidget(self.slider)
        layout.setAlignment(self.slider, Qt.AlignCenter)

        layout.addWidget(self.channel_min_value_label)
        layout.setAlignment(self.channel_min_value_label, Qt.AlignCenter)

        layout.addWidget(ch_label)
        layout.setAlignment(ch_label, Qt.AlignCenter)

        layout.addWidget(self.channel_value_label)
        layout.setAlignment(self.channel_value_label, Qt.AlignCenter)

        layout.addStretch() 

        self.setLayout(layout)
    
    def update_channel_value(self, value):
        self.slider.setValue(value)
        self.channel_value_label.setText(f'{value}')
        self.channel_max_value_label.setText(f'{self.slider.max_value}')
        self.channel_min_value_label.setText(f'{self.slider.min_value}')
    
    def setValid(self, valid):
        self.slider.setValid(valid)
    
class RcQualityWidget(QWidget):
    def __init__(self, parent=None):
        super(RcQualityWidget, self).__init__(parent)
        self.quality = 0 

    def set_quality(self, quality):
        self.quality = quality
        self.update()  # Trigger a repaint

    def paintEvent(self, event):
        painter = QPainter(self)

        pen = QPen()
        pen.setWidth(1) 
        pen.setColor(QColor(0, 0, 0))
        painter.setPen(pen)

        num_filled = int(self.quality / 255 * 10)

        rect_width = self.width() / 12
        rect_height = self.height() - pen.width() 
        gap = rect_width / 6 

        for i in range(10):
            if i < num_filled:
                painter.setBrush(QColor(0, 255, 0))  # Green for filled rectangles
            else:
                painter.setBrush(QColor(255, 255, 255))  # white for empty rectangles

            rect = QRectF(i * (rect_width + gap), 0, rect_width, rect_height)
            painter.drawRect(rect)

class RcInfoWidget(QWidget):
    def __init__(self, id, parent=None):
        super(RcInfoWidget, self).__init__(parent)

        self.setMinimumHeight(160)

        self.id = id
        self.status = -1 
        self.rcin = []

        layout = QVBoxLayout() 
        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        sliders_layout = QHBoxLayout()

        self.id_label = QLabel(f'ID: {self.id} |')
        info_layout.addWidget(self.id_label)

        self.status_label = QLabel()
        info_layout.addWidget(self.status_label)

        self.channel_num_label = QLabel()
        info_layout.addWidget(self.channel_num_label)

        self.quality_label = QLabel()
        self.quality_label.setFixedWidth(90)
        info_layout.addWidget(self.quality_label)

        self.rc_quality_widget = RcQualityWidget()
        self.rc_quality_widget.setFixedWidth(150)
        self.rc_quality_widget.setMaximumHeight(20)
        info_layout.addWidget(self.rc_quality_widget)

        info_layout.addStretch(1) 

        bind_button = QPushButton('Bind') 
        bind_button.clicked.connect(self.handle_rc_bind)
        info_layout.addWidget(bind_button)

        self.sliders = []
        self.slider_texts = []
        for i in range(DRONECAN_MAX_RC_CHANNELS):
            slider = ChannelSliderItem(i+1)
            self.sliders.append(slider)
            sliders_layout.addWidget(slider)

        layout.addLayout(info_layout)
        layout.addLayout(sliders_layout)
        self.setLayout(layout)
    
    def handle_rc_bind(self):
        print(f'Bind RC ID: {self.id}')

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen()
        pen.setWidth(1) 
        pen.setColor(QColor(0, 0, 0))
        painter.setPen(pen)

        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
    
    def get_id_str(self):
        return f'ID: {self.id} |'
    
    def get_status_str(self):
        status_str = 'Status: ' 
        if self.status == STATUS_QUALITY_VALID:
            status_str += "Vaild"
        elif self.status == STATUS_FAILSAFE:
            status_str += "Failsafe"
        else:
            status_str += "Unknown"
        status_str += ' |'
        return status_str
    
    def get_channel_qty(self):
        return len(self.rcin)

    def get_sliders(self):
        return self.sliders
    
    def update_display_channels(self, value):
        for i, slider in enumerate(self.get_sliders()):
            slider.setVisible(i < value)
        
    def update_info(self, status, quality, rcin):
        self.status = status
        self.quality = quality
        self.rcin = rcin

        self.status_label.setText(self.get_status_str())
        self.channel_num_label.setText(f'CH: {self.get_channel_qty()} |')
        self.quality_label.setText(f'Quality: {self.quality} ')
        self.rc_quality_widget.set_quality(quality)

        for i in range(DRONECAN_MAX_RC_CHANNELS):
            if i < len(rcin):
                self.sliders[i].setValid(True)
                self.sliders[i].update_channel_value(rcin[i])
            else:
                self.sliders[i].setValid(False)
                self.sliders[i].update_channel_value(CHANNEL_CENTER_VALUE)

class RcPanel(QDialog):
    update_values_signal = pyqtSignal(list)

    def __init__(self, parent, node):
        super(RcPanel, self).__init__(parent)
        self.setWindowTitle('RC Panel')
        self.setAttribute(Qt.WA_DeleteOnClose)

        self._node = node

        self.display_channels = DEFAULT_DISPLAY_CHANNELS

        setting_layout = QHBoxLayout()
        self.display_channel_spinbox = QSpinBox()
        self.display_channel_spinbox.setRange(1, DRONECAN_MAX_RC_CHANNELS)
        self.display_channel_spinbox.setValue(self.display_channels) 
        self.display_channel_spinbox.setFixedWidth(50)
        self.display_channel_spinbox.valueChanged.connect(self.handle_display_channels_value_changed)

        setting_layout.addWidget(QLabel('Display Channels:'))
        setting_layout.addWidget(self.display_channel_spinbox)
        setting_layout.addStretch(1) 

        self.idle_content = QLabel('No RC Instance Available.')

        self.rc_layout = QVBoxLayout()
        self.rc_layout.addWidget(self.idle_content)

        self.rc_instances = {} 

        layout = QVBoxLayout()

        layout.addLayout(setting_layout)
        layout.addLayout(self.rc_layout)

        self.setLayout(layout)

        self.update_values_signal.connect(self.update_channel_values)
        self._node.add_handler(dronecan.dronecan.sensors.rc.RCInput, self.handle_RCInput)

    def handle_RCInput(self, msg):
        rc_status = []
        rc_status.append(msg.message.id)
        rc_status.append(msg.message.status)
        rc_status.append(msg.message.quality)
        rc_status.append(msg.message.rcin)
        if not sip.isdeleted(self):
            self.update_values_signal.emit(rc_status)

    def update_channel_values(self, rc_status):
        rc_id = rc_status[0]
        rc_instance = self.rc_instances.get(rc_id, None)
        if rc_instance is None:
            rc_instance = RcInfoWidget(rc_id)
            rc_instance.setMinimumHeight(200)
            rc_instance.update_display_channels(self.display_channels)
            self.rc_instances[rc_id] = rc_instance
            self.rc_layout.addWidget(rc_instance)

        rc_instance.update_info(rc_status[1], rc_status[2], rc_status[3])
        self.idle_content.hide()

    def handle_display_channels_value_changed(self, value):
        self.display_channels = value
        for rc_instance in self.rc_instances.values():
            rc_instance.update_display_channels(value)
        self.adjustSize()

    def __del__(self):
        global _singleton
        _singleton = None

    def closeEvent(self, event):
        super(RcPanel, self).closeEvent(event)
        self.__del__()

def spawn(parent, node):
    global _singleton
    if _singleton is None:
        try:
            _singleton = RcPanel(parent, node)
        except Exception as ex:
            print(ex)

    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()

    return _singleton

get_icon = partial(get_icon, 'fa6s.asterisk')