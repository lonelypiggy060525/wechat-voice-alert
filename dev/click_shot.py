"""Click a point inside the app window and capture the window afterwards."""
import ctypes
import sys
import time
from ctypes import wintypes

u = ctypes.windll.user32

TITLE = "微信语音提醒"
out = sys.argv[1]
rx, ry = int(sys.argv[2]), int(sys.argv[3])

h = u.FindWindowW("TkTopLevel", TITLE)
r = wintypes.RECT()
u.GetWindowRect(h, ctypes.byref(r))
u.SetForegroundWindow(h)
time.sleep(0.4)
u.SetCursorPos(r.left + rx, r.top + ry)
time.sleep(0.15)
u.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.05)
u.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(0.6)

import subprocess
subprocess.run([sys.executable, "dev/tools_shot.py", TITLE, out], cwd=".")
print("clicked", rx, ry, "->", out)
