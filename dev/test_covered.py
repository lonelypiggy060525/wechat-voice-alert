"""Test: does PrintWindow capture WeChat while it is covered by another window?"""
import sys
import time
import ctypes
from ctypes import wintypes

from PIL import Image

sys.path.insert(0, ".")
from winocr import ocr_image

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BI(ctypes.Structure):
    _fields_ = [("bmiHeader", BIH), ("bmiColors", wintypes.DWORD * 3)]


def capture(hwnd, path):
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    dc = user32.GetWindowDC(hwnd)
    mdc = gdi32.CreateCompatibleDC(dc)
    bmp = gdi32.CreateCompatibleBitmap(dc, w, h)
    gdi32.SelectObject(mdc, bmp)
    ok = user32.PrintWindow(hwnd, mdc, 2)
    bi = BI()
    bi.bmiHeader.biSize = ctypes.sizeof(BIH)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    img.save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd)
    colors = img.getcolors(2000000)
    return img, bool(ok), len(colors) if colors else 999999


WX = 329612
user32.ShowWindow(WX, 4)   # show without activating
time.sleep(0.8)
r = wintypes.RECT()
user32.GetWindowRect(WX, ctypes.byref(r))
print("wechat rect:", r.left, r.top, r.right, r.bottom)

# bring another window to the foreground so WeChat is covered
hermes = user32.FindWindowW("Chrome_WidgetWin_1", "Hermes")
print("hermes hwnd:", hermes)
if hermes:
    user32.ShowWindow(hermes, 3)
    user32.SetForegroundWindow(hermes)
time.sleep(0.8)

img, ok, ncolors = capture(WX, "shot_covered.png")
print("covered capture: ok=%s size=%s colors=%d" % (ok, img.size, ncolors))
lines = ocr_image(img)
print("ocr lines:", len(lines))
for ln in lines[:18]:
    print(f"  y={ln['y']:4d} x={ln['x']:4d} {ln['text']}")
