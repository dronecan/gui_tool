#!/bin/bash

#
# Copyright (c) 2025 Applied Aeronautics
# Author: Ryan Johnston <rjohnston@appliedaeronautics.com>
#
# The MIT License (MIT)
#
# Copyright (c) 2016 UAVCAN
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


# DroneCAN GUI Tool - macOS App Bundle + DMG Builder
# Builds a standalone .app and DMG using PyInstaller and Homebrew Python.
# This version vendors qtwidgets and patches it to use PyQt5.

set -e  # Exit on any error

# Colors
RED='\033[0;31m'      
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}DroneCAN GUI Tool - macOS Builder${NC}"
echo -e "${GREEN}(PyInstaller + patched vendored qtwidgets)${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BUILD_DIR="$HOME/dronecan_build_pyinstaller"
REPO_URL="https://github.com/DroneCAN/gui_tool.git"
BRANCH="v1.2.28"
APP_NAME="DroneCAN GUI Tool"
DMG_NAME="DroneCAN-GUI-Tool-macOS"

# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------

if ! command -v brew &> /dev/null; then
    echo -e "${RED}Error: Homebrew is not installed.${NC}"
    echo "Install it from https://brew.sh/"
    exit 1
fi

if ! xcode-select -p &> /dev/null; then
    echo -e "${YELLOW}Installing Xcode Command Line Tools...${NC}"
    xcode-select --install
    echo -e "${YELLOW}Please complete the installation and run this script again.${NC}"
    exit 1
fi

# ---------------------------------------------------------------------------
# Prepare build directory
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Creating build directory...${NC}"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

# ---------------------------------------------------------------------------
# Install system dependencies via Homebrew
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Installing/updating Homebrew dependencies...${NC}"
brew install python@3.12 create-dmg || true
brew install qt@5 || true  # harmless if already installed

# Use Homebrew's Python 3.12 explicitly
PYTHON3="$(brew --prefix python@3.12)/bin/python3.12"

if [ ! -x "$PYTHON3" ]; then
    echo -e "${RED}Error: Python 3.12 not found at $PYTHON3${NC}"
    exit 1
fi

echo -e "${GREEN}Using Python: $PYTHON3${NC}"
"$PYTHON3" --version

# ---------------------------------------------------------------------------
# Create virtual environment
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Creating Python virtual environment...${NC}"
"$PYTHON3" -m venv venv
# shellcheck disable=SC1091
source venv/bin/activate

# ---------------------------------------------------------------------------
# Python dependencies
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Upgrading pip/setuptools/wheel...${NC}"
pip install --upgrade pip setuptools wheel

echo -e "${YELLOW}Installing Python dependencies...${NC}"
pip install PyQt5
pip install pyinstaller
pip install numpy
pip install dronecan
pip install "qtawesome==1.3.1"   # supports the 'fa.' prefix used by gui_tool
pip install python-can           # removes "No module named 'can'" warnings
pip install qtwidgets            # only used as a source to vendor from
pip install IPython

# ---------------------------------------------------------------------------
# Clone the DroneCAN GUI Tool repo
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Cloning DroneCAN GUI Tool repository...${NC}"
git clone "$REPO_URL" gui_tool
cd gui_tool
git checkout "$BRANCH"

# ---------------------------------------------------------------------------
# Install package in editable mode
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Installing DroneCAN GUI Tool (editable)...${NC}"
pip install -e .

# ---------------------------------------------------------------------------
# Vendor qtwidgets into dronecan_gui_tool and patch it to PyQt5
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Vendoring qtwidgets into dronecan_gui_tool (and patching to PyQt5)...${NC}"

# Find qtwidgets distribution directory WITHOUT importing it (no PySide2 issue)
QTW_SRC_DIR=$(python - << 'PY'
from importlib.metadata import distribution
import os
dist = distribution("qtwidgets")
# location of package root
for f in dist.files:
    # Find the directory that actually contains qtwidgets/__init__.py
    parts = str(f).split("/")
    if len(parts) >= 2 and parts[0] == "qtwidgets" and parts[1] == "__init__.py":
        root = dist.locate_file("qtwidgets")
        print(root.as_posix())
        break
PY
)

if [ -z "$QTW_SRC_DIR" ] || [ ! -d "$QTW_SRC_DIR" ]; then
    echo -e "${RED}Error: Could not locate qtwidgets package directory.${NC}"
    exit 1
fi

VENDOR_DIR="dronecan_gui_tool/vendor_qtwidgets"
rm -rf "$VENDOR_DIR"
mkdir -p "$VENDOR_DIR"

# Copy the entire qtwidgets package into vendor_qtwidgets
cp -R "$QTW_SRC_DIR"/. "$VENDOR_DIR/"

# Patch vendored qtwidgets to use PyQt5 instead of PySide2
echo -e "${YELLOW}Patching vendored qtwidgets to use PyQt5 instead of PySide2...${NC}"
find "$VENDOR_DIR" -name "*.py" -print0 | xargs -0 sed -i '.bak' \
    -e 's/from PySide2 import QtCore, QtGui, QtWidgets/from PyQt5 import QtCore, QtGui, QtWidgets/g' \
    -e 's/from PySide2.QtCore import/from PyQt5.QtCore import/g' \
    -e 's/from PySide2.QtGui import/from PyQt5.QtGui import/g' \
    -e 's/from PySide2.QtWidgets import/from PyQt5.QtWidgets import/g'

find "$VENDOR_DIR" -name "*.bak" -delete

# Now rewrite imports in dronecan_gui_tool to use the vendored copy
echo -e "${YELLOW}Rewriting qtwidgets imports in dronecan_gui_tool to use vendored version...${NC}"

# Replace "from qtwidgets import X" → "from .vendor_qtwidgets import X"
find dronecan_gui_tool -name "*.py" -print0 | xargs -0 sed -i '.bak' \
    -e 's/from qtwidgets import /from .vendor_qtwidgets import /g' \
    -e 's/^import qtwidgets$/from . import vendor_qtwidgets as qtwidgets/g' \
    -e 's/^import qtwidgets as qtwidgets$/from . import vendor_qtwidgets as qtwidgets/g'

find dronecan_gui_tool -name "*.bak" -delete

# ---------------------------------------------------------------------------
# Create launcher script
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Creating launcher script...${NC}"
cat > launcher.py << 'EOF'
#!/usr/bin/env python3
import sys
from multiprocessing import freeze_support

if __name__ == '__main__':
    # Required for PyInstaller + multiprocessing on macOS
    freeze_support()
    from dronecan_gui_tool.main import main
    sys.exit(main())
EOF

chmod +x launcher.py
MAIN_SCRIPT="launcher.py"
echo -e "${GREEN}Created launcher script: $MAIN_SCRIPT${NC}"

# ---------------------------------------------------------------------------
# Create PyInstaller spec file (no top-level qtwidgets)
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Creating PyInstaller spec file...${NC}"
cat > dronecan_gui.spec << EOF
# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
from PyInstaller.building.datastruct import TOC

block_cipher = None

# -------------------------------------------------------------------------
# Monkey-patch os.symlink to ignore "already exists" errors
# (common with Qt frameworks on macOS when collected multiple times)
# -------------------------------------------------------------------------
_real_symlink = os.symlink

def _safe_symlink(src, dst, *args, **kwargs):
    try:
        _real_symlink(src, dst, *args, **kwargs)
    except FileExistsError:
        print(f"[spec] symlink already exists, skipping: {src} -> {dst}")

os.symlink = _safe_symlink

# -------------------------------------------------------------------------
# Collect package data
# -------------------------------------------------------------------------
datas = collect_data_files('dronecan_gui_tool')
datas += collect_data_files('dronecan')

# qtwidgets code is vendored under dronecan_gui_tool.vendor_qtwidgets,
# so we don't touch the top-level qtwidgets package at all.

# -------------------------------------------------------------------------
# Collect submodules for core packages (including vendored qtwidgets)
# -------------------------------------------------------------------------
hiddenimports = []
hiddenimports += collect_submodules('dronecan_gui_tool')
hiddenimports += collect_submodules('dronecan')
hiddenimports += collect_submodules('PyQt5')

hiddenimports += [
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtSvg',
    'PyQt5.sip',
    'numpy',
    'qtawesome',
    'IPython',
    'pkg_resources.py2_warn',
]

a = Analysis(
    ['$MAIN_SCRIPT'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'scipy', 'pandas', 'tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='$APP_NAME',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# -------------------------------------------------------------------------
# Deduplicate TOC entries to avoid duplicate Qt symlink collisions
# -------------------------------------------------------------------------
def dedupe_toc(items):
    seen = set()
    deduped = []
    for item in items:
        dest_name = item[0]
        if dest_name in seen:
            print(f"[spec] Removing duplicate entry: {dest_name}")
            continue
        seen.add(dest_name)
        deduped.append(item)
    return TOC(deduped)

binaries_deduped = dedupe_toc(a.binaries)
datas_deduped = dedupe_toc(a.datas)
zipfiles_deduped = dedupe_toc(a.zipfiles)

coll = COLLECT(
    exe,
    binaries_deduped,
    zipfiles_deduped,
    datas_deduped,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='$APP_NAME',
)

app = BUNDLE(
    coll,
    name='$APP_NAME.app',
    icon=None,
    bundle_identifier='org.dronecan.gui_tool',
    info_plist={
        'CFBundleName': '$APP_NAME',
        'CFBundleDisplayName': '$APP_NAME',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': 'True',
        'LSMinimumSystemVersion': '10.13.0',
        'NSHumanReadableCopyright': 'Copyright © 2024 DroneCAN Contributors',
    },
)
EOF

# ---------------------------------------------------------------------------
# Clean previous PyInstaller artifacts
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Cleaning previous builds and PyInstaller cache...${NC}"
rm -rf build dist
rm -rf "$HOME/Library/Application Support/pyinstaller" 2>/dev/null || true

# ---------------------------------------------------------------------------
# Build the application
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Building application bundle with PyInstaller...${NC}"
pyinstaller --clean --noconfirm dronecan_gui.spec

# ---------------------------------------------------------------------------
# Verify build
# ---------------------------------------------------------------------------
if [ ! -d "dist/$APP_NAME.app" ]; then
    echo -e "${RED}Error: Application build failed!${NC}"
    echo "Check the build output above for errors."
    deactivate || true
    exit 1
fi

echo -e "${GREEN}Application bundle created successfully!${NC}"

# ---------------------------------------------------------------------------
# Quick run test (use the .app binary)
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Testing application (quick launch)...${NC}"
"dist/$APP_NAME.app/Contents/MacOS/$APP_NAME" --help > /dev/null 2>&1 || true
echo -e "${GREEN}Application test command executed (GUI may not show with --help).${NC}"

# ---------------------------------------------------------------------------
# Create DMG
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Creating DMG installer...${NC}"
DMG_PATH="$BUILD_DIR/$DMG_NAME.dmg"
rm -f "$DMG_PATH"

DMG_TEMP="$BUILD_DIR/dmg_temp"
rm -rf "$DMG_TEMP"
mkdir -p "$DMG_TEMP"

cp -R "dist/$APP_NAME.app" "$DMG_TEMP/"
ln -s /Applications "$DMG_TEMP/Applications"

cat > "$DMG_TEMP/README.txt" << EOF2
DroneCAN GUI Tool
==================

Installation:
1. Drag "$APP_NAME" to the Applications folder
2. First launch: Right-click the app and select "Open"
   (this is required for unsigned applications)
3. Subsequent launches: Double-click normally

Requirements:
- macOS 10.13 or later
- No additional software needed (all dependencies included)

Support:
- Documentation: https://dronecan.github.io/GUI_Tool/
- Issues: https://github.com/DroneCAN/gui_tool/issues

Note: This is an unsigned application. On first launch, macOS may
show a security warning. Right-click and select "Open" to bypass.
EOF2

echo -e "${YELLOW}Packaging DMG with create-dmg...${NC}"
create-dmg \
    --volname "$APP_NAME" \
    --window-pos 200 120 \
    --window-size 800 400 \
    --icon-size 100 \
    --icon "$APP_NAME.app" 200 190 \
    --hide-extension "$APP_NAME.app" \
    --app-drop-link 600 185 \
    "$DMG_PATH" \
    "$DMG_TEMP" \
    2>/dev/null || \
create-dmg \
    --volname "$APP_NAME" \
    --window-pos 200 120 \
    --window-size 800 400 \
    --icon-size 100 \
    "$DMG_PATH" \
    "$DMG_TEMP"

rm -rf "$DMG_TEMP"

APP_SIZE=$(du -sh "dist/$APP_NAME.app" | cut -f1)
DMG_SIZE=$(du -h "$DMG_PATH" | cut -f1)

# ---------------------------------------------------------------------------
# Install app to /Applications
# ---------------------------------------------------------------------------
echo -e "${YELLOW}Copying application to /Applications...${NC}"

APP_SOURCE_PATH="$BUILD_DIR/gui_tool/dist/$APP_NAME.app"
APP_DEST_PATH="/Applications/$APP_NAME.app"

# Remove old version if it exists
if [ -d "$APP_DEST_PATH" ]; then
    echo -e "${YELLOW}Removing existing application at $APP_DEST_PATH...${NC}"
    rm -rf "$APP_DEST_PATH"
fi

# Copy the new build
cp -R "$APP_SOURCE_PATH" "/Applications/"

echo -e "${GREEN}Installed $APP_NAME to /Applications${NC}"

# ---------------------------------------------------------------------------
# Final output
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Build completed successfully!${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

echo -e "${GREEN}Application bundle (build artifact):${NC}"
echo -e "  $BUILD_DIR/gui_tool/dist/$APP_NAME.app"
echo -e "  Size: $APP_SIZE"
echo ""

echo -e "${GREEN}Application installed to:${NC}"
echo -e "  /Applications/$APP_NAME.app"
echo -e "  ${YELLOW}(You can now launch it like any normal macOS app)${NC}"
echo ""

echo -e "${GREEN}DMG installer:${NC}"
echo -e "  $DMG_PATH"
echo -e "  Size: $DMG_SIZE"
echo ""

echo -e "${YELLOW}To launch manually from Terminal:${NC}"
echo -e "  open '/Applications/$APP_NAME.app'"
echo ""

echo -e "${YELLOW}Installation instructions for end users (DMG):${NC}"
echo -e "  1. Mount the DMG"
echo -e "  2. Drag \"$APP_NAME\" to Applications"
echo -e "  3. First launch: Right-click → Open (to bypass Gatekeeper)"
echo ""

echo -e "${GREEN}Note:${NC} This build includes all dependencies (including patched vendored qtwidgets using PyQt5)."
echo ""

deactivate
echo -e "${GREEN}Done!${NC}"
