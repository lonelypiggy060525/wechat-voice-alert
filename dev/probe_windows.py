"""Enumerate every top-level window owned by Weixin.exe processes (incl. hidden)."""
import ctypes
from ctypes import wintypes
import subprocess, re

user32 = ctypes.WinDLL("user32", use_last_error=True)

# PIDs of Weixin.exe
out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True).stdout.decode("gbk", "replace")
pids = set()
for line in out.splitlines():
    parts = [p.strip('"') for p in line.split('","')]
    if parts and parts[0].lower() in ("weixin.exe", "wechatappex.exe"):
        pids.add(int(parts[1]))
print("weixin pids:", sorted(pids))

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
rows = []

def cb(hwnd, lparam):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if pid.value not in pids:
        return True
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    n = user32.GetWindowTextLengthW(hwnd)
    title = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, title, n + 1)
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    rows.append((hwnd, pid.value, cls.value, title.value, (r.left, r.top, r.right, r.bottom), bool(user32.IsWindowVisible(hwnd))))
    return True

user32.EnumWindows(WNDENUMPROC(cb), 0)
for row in sorted(rows, key=lambda x: (x[1], x[2])):
    print(row)
