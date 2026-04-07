#!/usr/bin/env python3
"""
USB2CAN setup script for DroneCAN GUI Tool

This script sets up the USB2CAN DLL for use with the DroneCAN GUI Tool.
It copies the appropriate DLL to a location where it can be found by python-can.
"""

import os
import shutil
import platform
import sys

def setup_usb2can_dll():
    """Copy the USB2CAN DLL to an accessible location"""
    print("Setting up USB2CAN DLL for DroneCAN GUI Tool...")
    
    # Get the current directory (should be the gui_tool root)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Determine the correct DLL based on architecture
    if platform.machine().lower() in ['amd64', 'x86_64', 'x64']:
        dll_source = os.path.join(current_dir, 'bin', 'usb2can_canal_v2.0.0', 'x64', 'Release', 'usb2can.dll')
        arch = 'x64'
    else:
        dll_source = os.path.join(current_dir, 'bin', 'usb2can_canal_v2.0.0', 'x86', 'Release', 'usb2can.dll')
        arch = 'x86'
    
    if not os.path.exists(dll_source):
        print(f"Error: USB2CAN DLL not found at {dll_source}")
        return False
    
    # Copy to the current directory (where the script is run from)
    dll_dest = os.path.join(current_dir, 'usb2can.dll')
    
    try:
        shutil.copy2(dll_source, dll_dest)
        print(f"Successfully copied {arch} USB2CAN DLL to {dll_dest}")
        return True
    except Exception as e:
        print(f"Error copying DLL: {e}")
        return False

if __name__ == "__main__":
    success = setup_usb2can_dll()
    if success:
        print("\n✅ USB2CAN setup completed successfully!")
        print("You can now use 8devices USB2CAN adapters with the DroneCAN GUI Tool.")
    else:
        print("\n❌ USB2CAN setup failed!")
        sys.exit(1)