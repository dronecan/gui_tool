'''
 a table display widget that takes a key to detemine table row
'''
import dronecan
from PyQt5.QtWidgets import QTableWidget, QTableWidgetItem
from PyQt5.QtCore import Qt, QTimer
import time


class TableDisplay(QTableWidget):
    '''table viewer'''
    def __init__(self, headers, expire_time=2.0):
        QTableWidget.__init__(self, 0, len(headers))
        self.headers = headers
        self.row_keys = []
        self.timestamps = {}
        self.setHorizontalHeaderLabels(self.headers)
        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.expire_time = expire_time
        self.show()
        self.data = {}
        if self.expire_time is not None:
            QTimer.singleShot(int(expire_time*500), self.check_expired)

    def update(self, row_key, row):
        '''update a row'''
        if not row_key in self.row_keys:
            # new row
            self.timestamps[row_key] = time.time()
            self.insertRow(len(self.row_keys))
            self.row_keys.append(row_key)

        self.timestamps[row_key] = time.time()
        row_idx = self.row_keys.index(row_key)
        self.data[row_key] = row
        for i in range(len(row)):
            self.setItem(row_idx, i, QTableWidgetItem(str(row[i])))

        self.resizeColumnsToContents()
        self.resizeRowsToContents()
        self.show()

    def get(self, row_key):
        '''get current data for a row'''
        return self.data.get(row_key,None)

    def get_selected(self):
        '''get the selected row key'''
        row = self.currentRow()
        if row is None:
            return None
        return self.row_keys[row]

    def remove_row(self, row_key):
        '''remove a row'''
        if not row_key in self.row_keys:
            return
        row_idx = self.row_keys.index(row_key)
        if row_idx != -1:
            self.row_keys.pop(row_idx)
            self.removeRow(row_idx)

    def check_expired(self):
        '''check for expired rows'''
        keys = list(self.timestamps.keys())
        now = time.time()
        for key in keys:
            if now - self.timestamps[key] >= self.expire_time:
                # remove old rows
                self.timestamps.pop(key)
                self.remove_row(key)
        QTimer.singleShot(int(self.expire_time*500), self.check_expired)


