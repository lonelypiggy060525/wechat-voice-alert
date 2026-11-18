"""Find the app window by title and capture it (PrintWindow), then save a PNG."""
import ctypes
import sys
import time
from ctypes import wintypes

from PIL import Image

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

TITLE = sys.argv[1] if len(sys.argv) > 1 else "微信语音提醒"
OUT = sys.argv[2] if len(sys.argv) > 2 else "shot_app.png"

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
found = []


def cb(hwnd, _):
    n = user32.GetWindowTextLengthW(hwnd)
    if n == 0:
        return True
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    if buf.value == TITLE and user32.IsWindowVisible(hwnd):
        found.append(hwnd)
    return True


user32.EnumWindows(WNDENUMPROC(cb), 0)
if not found:
    print("window not found")
    sys.exit(1)
hwnd = found[0]
print("hwnd", hwnd)
user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)  # topmost, no move
time.sleep(0.4)
r = wintypes.RECT()
user32.GetWindowRect(hwnd, ctypes.byref(r))
w, h = r.right - r.left, r.bottom - r.top
print("size", w, h)


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BI(ctypes.Structure):
    _fields_ = [("bmiHeader", BIH), ("bmiColors", wintypes.DWORD * 3)]


dc = user32.GetWindowDC(hwnd)
mdc = gdi32.CreateCompatibleDC(dc)
bmp = gdi32.CreateCompatibleBitmap(dc, w, h)
gdi32.SelectObject(mdc, bmp)
print("printwindow", user32.PrintWindow(hwnd, mdc, 2))
bi = BI()
bi.bmiHeader.biSize = ctypes.sizeof(BIH)
bi.bmiHeader.biWidth = w
bi.bmiHeader.biHeight = -h
bi.bmiHeader.biPlanes = 1
bi.bmiHeader.biBitCount = 32
buf = ctypes.create_string_buffer(w * h * 4)
gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
img.save(OUT)
print("saved", OUT, img.size)
user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0001 | 0x0002)
