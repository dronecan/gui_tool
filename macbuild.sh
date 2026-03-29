#!/bin/bash
# macOS build script for DroneCAN GUI Tool
# Produces a .app bundle and a .dmg installer in the dist/ folder.
# Requirements: Python 3.9+

set -e

python3 --version

# Create and activate a clean virtual environment
python3 -m venv venv
source venv/bin/activate

python3 -m pip install -U pip
python3 -m pip install -U py2app
python3 -m pip install -U pymavlink
python3 -m pip install -U python-can
python3 -m pip install -U .

APP_NAME="DroneCAN GUI Tool"

# Clean previous build artifacts
rm -rf build dist

# Build the .app bundle with py2app
python3 setup_mac.py py2app

# Package the .app into a .dmg
hdiutil create \
    -volname "${APP_NAME}" \
    -srcfolder "dist/${APP_NAME}.app" \
    -ov \
    -format UDZO \
    "dist/DroneCAN_GUI_Tool.dmg"

echo "Build complete. Artifact: dist/DroneCAN_GUI_Tool.dmg"
ls -lh dist/
