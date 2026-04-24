#
# Copyright (C) 2016  UAVCAN Development Team  <uavcan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

from ..widgets import show_error

# TODO: Load all inner modules automatically. This is not really easy because we have to support freezing.
from . import esc_panel
from . import actuator_panel
from . import RTK_panel
from . import serial_panel
from . import stats_panel
from . import RemoteID_panel
from . import hobbywing_esc
from . import rc_panel

import importlib.util

class PanelDescriptor:
    def __init__(self, module):
        self.name = module.PANEL_NAME
        self._module = module

    def get_icon(self):
        # noinspection PyBroadException
        try:
            return self._module.get_icon()
        except Exception:
            pass

    def safe_spawn(self, parent, node):
        try:
            return self._module.spawn(parent, node)
        except Exception as ex:
            show_error('Panel error', 'Could not spawn panel', ex)

def import_panel(name):
    """Given a package name like 'foo.bar.quux', imports the package
    and returns the desired module."""
    spec = importlib.util.find_spec(name)
    mod = None
    if spec is None:
        raise Exception(f"Module '{name}' not found!")
    else:
        mod = importlib.import_module(name)
        print(f"Successfully imported {name} from {mod.__file__}")
    return PluginPanelDescriptor(mod)

class PluginPanelDescriptor(PanelDescriptor):
    def __init__(self, module):
        super().__init__(module)

        self.menu_path = getattr(module, "MENU_PATH", "")

PANELS = [
    PanelDescriptor(esc_panel),
    PanelDescriptor(actuator_panel),
    PanelDescriptor(RTK_panel),
    PanelDescriptor(serial_panel),
    PanelDescriptor(stats_panel),
    PanelDescriptor(RemoteID_panel),
    PanelDescriptor(hobbywing_esc),
    PanelDescriptor(rc_panel)
]
