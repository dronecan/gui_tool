DroneCAN GUI Tool 
=======================

DroneCAN GUI Tool is a cross-platform (Windows/Linux/OSX) application for UAVCAN v0.9 and/or DroneCAN V1 management and diagnostics.

[Read the docs at **https://dronecan.org**](https://dronecan.org).

[Ask questions at **https://ardupilot.org/copter/docs/common-contact-us.html**](https://ardupilot.org/copter/docs/common-contact-us.html).

Read installation instructions:

- [**GNU/LINUX**](#installing-on-gnulinux)
- [**WINDOWS**](#installing-on-windows)
- [**MACOS**](#installing-on-macos)

![DroneCAN GUI Tool screenshot](screenshot.png "DroneCAN GUI Tool screenshot")

## Installing on GNU/Linux

The general approach is simple:

1. Install PyQt6 for Python 3 using your OS' package manager (e.g. APT).
2. Install the application itself from Git via PIP:
`pip3 install git+https://github.com/DroneCAN/gui_tool@master`
(it is not necessary to clone this repository manually).
Alternatively, if you're a developer and you want to install your local copy, use `pip3 install .`.

It also may be necessary to install additional dependencies, depending on your distribution (see details below).

Once the application is installed, you should see new desktop entries available in your desktop menu;
also a new executable `dronecan_gui_tool` will be available in your `PATH`.
If your desktop environment doesn't update the menu automatically, you may want to do it manually, e.g.
by invoking `sudo update-desktop-database` (command depends on the distribution).

It is also recommended to install Matplotlib - it is not used by the application itself,
but it may come in handy when using the embedded IPython console.

### Debian-based distributions

```bash
sudo apt-get install -y python3-pip python3-setuptools python3-wheel
sudo apt-get install -y python3-numpy python3-pyqt6 python3-pyqt6.qtsvg pyqt6-dev-tools git-core
python3 -m pip install git+https://github.com/DroneCAN/gui_tool@master
```

#### Troubleshooting

If installation fails with an error like below, try to install IPython directly with `python3 -m pip install ipython`:

> error: Setup script exited with error in ipython setup command:
> Invalid environment marker: sys_platform == "darwin" and platform_python_implementation == "CPython"

If you're still unable to install the package, please open a ticket.

### RPM-based distributions

*Maintainers wanted*

#### Fedora 29+
```bash
sudo dnf install python3-PyQt6
python3 -m pip install git+https://github.com/DroneCAN/gui_tool@master
```

## Installing on Windows

In order to install this application,
**download and install the latest `.msi` package from here: <https://firmware.ardupilot.org/Tools/CAN_GUI/>**.

### Building the MSI package

Please see the file winbuild.bat in this directory, or use the MSI file build by github actions on any commit

## Installing on macOS

OSX support is a bit lacking in the way that installation doesn't create an entry in the applications menu,
but this issue should be fixed someday in the future.
Other than that, everything appears to function more or less correctly.
If you have a choice, it is recommended to use Linux or Windows instead,
as these ports are supported much better at the moment.

### Homebrew option

* Install the Homebrew package manager for OSX.
* Run the following commands:

```bash
brew install python3
brew postinstall python3
pip3 install PyQt6
pip3 install git+https://github.com/DroneCAN/gui_tool@master
dronecan_gui_tool
```

### MacPorts option

Install XCode from App Store, install MacPorts from <https://www.macports.org/install.php>,
then run the commands below.
If you're prompted to install Command Line Developer Tools, agree.

```bash
sudo port selfupdate
sudo port install curl-ca-bundle py35-pip py35-pyqt6 py35-numpy
python3.5 -m pip install git+https://github.com/DroneCAN/gui_tool@master
```

We would like to provide prebuilt application packages instead of the mess above.
Contributions adding this capability would be welcome.

## Plugins

Plugins are custom panels that are loaded at startup and listed under the **Plugins** menu.
The first nine plugins are given the shortcuts `Ctrl+Alt+P` followed by `1` to `9`.

### Loading plugins

Plugins can be loaded from the plugins folder, `~/dronecan_gui_tool/plugins`, or from any
installed Python module:

```bash
# Load every plugin in ~/dronecan_gui_tool/plugins
dronecan_gui_tool --auto-load-plugins

# Load specific plugins by name (comma-separated, may be repeated)
dronecan_gui_tool --load-plugin my_panel,other_panel --load-plugin mypackage.my_panel
```

- The plugins folder is not created automatically.
- `--load-plugin` looks in the plugins folder first, then falls back to installed modules.
  This works without `--auto-load-plugins`.
- Files and folders starting with `_` (e.g. `_helpers.py`) are not loaded by `--auto-load-plugins`.
  Use this for shared code, or to disable a plugin without deleting it.
- A plugin that fails to load is logged as an error and skipped; the tool still starts.

Plugins in the plugins folder are imported under the `dronecan_gui_tool_plugins` package, so they
cannot clash with installed modules of the same name. A plugin can be a single file (`my_panel.py`)
or a package (`my_panel/__init__.py`). A plugin split across several files must be a package and
use relative imports (`from . import helpers`), as a plain `import helpers` will not find sibling files.

When using a packaged build (e.g. the Windows MSI), plugins can only import the packages that are
bundled with the tool, such as `PyQt6` and `dronecan`.

### Writing a plugin

A plugin is a Python module that provides:

| Name | Required | Description |
|------|----------|-------------|
| `PANEL_NAME` | Yes | Name shown in the Plugins menu. |
| `spawn(parent, node)` | Yes | Called when the menu item is selected. Should open (or raise) the panel window and return it. |
| `get_icon()` | No | Returns a `QIcon` for the menu item. |
| `MENU_PATH` | No | Submenu path within the Plugins menu, e.g. `"Vendor/Sensors"`. |

Panels should keep a single window open, and remove any node handlers when that window closes.
Otherwise the handlers keep running in the background after the window is closed.

```python
# ~/dronecan_gui_tool/plugins/node_uptime.py
import dronecan
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout
from dronecan_gui_tool.widgets import get_icon as _get_icon

PANEL_NAME = 'Node Uptime'
MENU_PATH = 'Examples'

_singleton = None


class NodeUptimePanel(QDialog):
    def __init__(self, parent, node):
        super().__init__(parent)
        self.setWindowTitle(PANEL_NAME)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self._label = QLabel('Waiting for NodeStatus...', self)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)

        # Keep the handle so the handler can be removed when the window closes
        self._handler = node.add_handler(dronecan.uavcan.protocol.NodeStatus, self._on_node_status)

    def _on_node_status(self, e):
        self._label.setText(f'Node {e.transfer.source_node_id}: up {e.message.uptime_sec} s')

    def closeEvent(self, event):
        global _singleton
        self._handler.remove()
        _singleton = None
        super().closeEvent(event)


def spawn(parent, node):
    global _singleton
    if _singleton is None:
        _singleton = NodeUptimePanel(parent, node)
    _singleton.show()
    _singleton.raise_()
    _singleton.activateWindow()
    return _singleton


def get_icon():
    return _get_icon('fa6s.clock')
```

## Development

### Releasing new version

First, deploy the new version to PyPI. In order to do that, perform the following steps:

1. Update the version tuple in `version.py`, e.g. `1, 0`, and commit this change.
2. Create a new tag with the same version number as in the version file, e.g. `git tag -a 1.0 -m v1.0`.
3. Push to master: `git push && git push --tags`

Then, build a Windows MSI package using the instructions above, and upload the resulting MSI to
the distribution server.

### Code style

Please follow the existing code styles .

## History

Much of the development of this tool is based upon original work by
Pavel Kirienko and others from the UAVCAN Development Team. See
https://github.com/UAVCAN/gui_tool for contributors.

