#!/bin/bash
# Linux AppImage build script for DroneCAN GUI Tool
# Produces an AppImage in the dist/ folder.

set -e

# Note: If APPIMAGETOOL_RELEASE is updated to a newer version, you MUST also
# update APPIMAGETOOL_SHA256 to match the checksum of the new binary.
APPIMAGETOOL_RELEASE="1.9.1"
APPIMAGETOOL_SHA256="ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0"

echo "Building DroneCAN GUI Tool AppImage..."

python3 --version

# Create and activate a clean virtual environment
python3 -m venv --clear venv
source venv/bin/activate

# Install pyinstaller and other dependencies
python3 -m pip install -U pip pyinstaller
python3 -m pip install -U pymavlink
python3 -m pip install -U python-can
python3 -m pip install -U .

# Clean previous build artifacts
rm -rf build dist/DroneCAN_GUI_Tool dist/*.AppImage AppDir

# Build the binary folder with PyInstaller
echo "Running PyInstaller..."
pyinstaller -y --name "DroneCAN_GUI_Tool" --windowed --icon icons/logo.ico \
    --collect-all dronecan \
    --collect-all dronecan_gui_tool \
    --collect-all pymavlink \
    bin/dronecan_gui_tool

echo "Setting up AppDir..."
mkdir -p AppDir/usr/bin
cp -r dist/DroneCAN_GUI_Tool/* AppDir/usr/bin/
cp dronecan_gui_tool/icons/dronecan_gui_tool.png AppDir/dronecan_gui_tool.png

# Create AppRun
cat << 'EOF' > AppDir/AppRun
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/DroneCAN_GUI_Tool" "$@"
EOF
chmod +x AppDir/AppRun

# Create Desktop file
cat << 'EOF' > AppDir/dronecan_gui_tool.desktop
[Desktop Entry]
Name=DroneCAN GUI Tool
Exec=AppRun
Icon=dronecan_gui_tool
Type=Application
Categories=Development;Utility;
EOF

# Download appimagetool if not exists
if [ ! -f "appimagetool-x86_64.AppImage" ]; then
    echo "Downloading appimagetool..."
    wget -q "https://github.com/AppImage/appimagetool/releases/download/${APPIMAGETOOL_RELEASE}/appimagetool-x86_64.AppImage"
    echo "${APPIMAGETOOL_SHA256}  appimagetool-x86_64.AppImage" | sha256sum -c -
    chmod +x appimagetool-x86_64.AppImage
fi

echo "Packaging AppImage..."
# Create the AppImage
./appimagetool-x86_64.AppImage --appimage-extract-and-run AppDir dist/DroneCAN_GUI_Tool-x86_64.AppImage

echo "Build complete. Artifact: dist/DroneCAN_GUI_Tool-x86_64.AppImage"
ls -lh dist/
