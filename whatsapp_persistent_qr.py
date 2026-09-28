import os
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))
sync_script = os.path.join(base_dir, "whatsapp_native_sync.py")

if os.path.exists(sync_script):
    from whatsapp_native_sync import start_whatsapp_sync
    start_whatsapp_sync()