#
# Copyright (C) 2016  UAVCAN Development Team  <uavcan.org>
#
# This software is distributed under the terms of the MIT License.
#
# Author: Pavel Kirienko <pavel.kirienko@zubax.com>
#

from logging import getLogger
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
from . import hardpoints_panel
from . import circuit_status_panel

import importlib
import importlib.util
import pkgutil
import sys
import types

logger = getLogger(__name__)

# Package that modules in the user plugins folder are imported under, so they
# cannot shadow (or be shadowed by) modules on sys.path.
PLUGIN_PACKAGE = "dronecan_gui_tool_plugins"

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

def register_plugin_dir(path):
    """
    Registers the given folder as the PLUGIN_PACKAGE package, allowing the modules within it to be loaded with import_panel().
    """
    pkg = types.ModuleType(PLUGIN_PACKAGE)
    pkg.__path__ = [str(path)]
    sys.modules[PLUGIN_PACKAGE] = pkg

def discover_user_plugins():
    """
    Returns a sorted list of all modules and packages in the registered user plugins folder.

    Modules/Packages starting with an underscore are skipped.
    """
    pkg = sys.modules.get(PLUGIN_PACKAGE)
    if pkg is None:
        return []
    return sorted(m.name for m in pkgutil.iter_modules(pkg.__path__) if not m.name.startswith("_"))

def _find_user_plugin(name):
    if PLUGIN_PACKAGE not in sys.modules:
        return None
    full_name = f"{PLUGIN_PACKAGE}.{name}"
    try:
        return full_name if importlib.util.find_spec(full_name) else None
    except ModuleNotFoundError:
        return None

def import_panel(name):
    """
    Given a module name like 'foo.bar.quux', imports the module and returns a PluginPanelDescriptor for it.

    Modules in the user plugins folder take precedence over installed modules.
    """
    name = _find_user_plugin(name) or name
    mod = importlib.import_module(name)
    if not hasattr(mod, "PANEL_NAME"):
        raise ImportError(f"Plugin '{name}' is not a valid panel - missing 'PANEL_NAME'")

    if not callable(getattr(mod, "spawn", None)):
        raise ImportError(f"Plugin '{name}' is not a valid panel - missing 'spawn()'")

    logger.info("Loaded plugin %s from %s", name, mod.__file__)
    return PluginPanelDescriptor(mod)

class PluginPanelDescriptor(PanelDescriptor):
    def __init__(self, module):
        super().__init__(module)

        self.module_name = module.__name__
        self.menu_path = getattr(module, "MENU_PATH", "")

PANELS = [
    PanelDescriptor(esc_panel),
    PanelDescriptor(actuator_panel),
    PanelDescriptor(RTK_panel),
    PanelDescriptor(serial_panel),
    PanelDescriptor(stats_panel),
    PanelDescriptor(RemoteID_panel),
    PanelDescriptor(hobbywing_esc),
    PanelDescriptor(rc_panel),
    PanelDescriptor(hardpoints_panel),
    PanelDescriptor(circuit_status_panel)
]
