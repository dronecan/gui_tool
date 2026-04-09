#!/usr/bin/env python3
"""
Test script to specifically check USB2CAN interface detection
"""

import sys
import logging

# Setup logging to see warnings and errors
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

print("=== Testing USB2CAN Interface Detection ===")
print(f"Python version: {sys.version}")

try:
    # Import the setup window module which handles interface detection
    sys.path.insert(0, r'C:\Users\bluea\OneDrive\Documents\GitHub\gui_tool')
    from dronecan_gui_tool.setup_window import list_ifaces
    
    print("\n=== Calling list_ifaces() ===")
    interfaces = list_ifaces()
    
    print(f"Found {len(interfaces)} interfaces:")
    usb2can_found = False
    
    for i, (display_name, interface_spec) in enumerate(interfaces.items()):
        print(f"  {i+1}. '{display_name}' -> '{interface_spec}'")
        if 'usb2can' in display_name.lower() or 'usb2can:' in interface_spec:
            print(f"     *** USB2CAN INTERFACE FOUND! ***")
            usb2can_found = True
    
    if not usb2can_found:
        print("\n⚠  No USB2CAN interfaces were detected!")
        print("   This means the 8devices USB2CAN adapter is not showing up.")
    else:
        print("\n✅ USB2CAN interface detection is working!")
    
except Exception as e:
    print(f"✗ Error during interface detection: {e}")
    import traceback
    traceback.print_exc()

print("\n=== Test completed ===")