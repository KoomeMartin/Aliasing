import os
import sys
import ctypes

try:                                    # crisp text on high-DPI Windows displays
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:                       # noqa: BLE001
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.app import main

if __name__ == "__main__":
    main()
