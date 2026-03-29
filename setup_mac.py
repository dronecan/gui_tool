"""
py2app build configuration for macOS .app bundle.
Usage: python3 setup_mac.py py2app
"""
import os
import site

PACKAGE_NAME = 'dronecan_gui_tool'
APP_NAME = 'DroneCAN GUI Tool'

# Locate the dronecan dsdl_specs data files
site_packages = site.getsitepackages()[0]
dsdl_specs = os.path.join(site_packages, 'dronecan', 'dsdl_specs')

OPTIONS = {
    'argv_emulation': False,
    'packages': [
        PACKAGE_NAME,
        'dronecan',
        'qtwidgets',
        'pyqtgraph',
        'qtawesome',
        'qtconsole',
        'ipykernel',
        'jupyter_client',
        'zmq',
        'pygments',
        'traitlets',
    ],
    'includes': [
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.QtSvg',
        'PyQt5.QtPrintSupport',
        'PyQt5.QtSerialPort',
    ],
    'resources': [dsdl_specs],
    'iconfile': 'icons/logo.icns',
    'plist': {
        'CFBundleName': APP_NAME,
        'CFBundleDisplayName': APP_NAME,
        'CFBundleIdentifier': 'org.dronecan.gui-tool',
        'NSHighResolutionCapable': True,
    },
}

from setuptools import setup

setup(
    name=APP_NAME,
    app=['bin/dronecan_gui_tool'],
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
    data_files=[('icons', ['icons/logo.icns'])],
)
