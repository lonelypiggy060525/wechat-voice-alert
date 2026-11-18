"""Briefly show WeChat (no focus), capture main window, re-minimize, OCR the left chat list."""
import asyncio
import ctypes
import time
from ctypes import wintypes

from PIL import Image
import winsdk.windows.media.ocr as ocr
import winsdk.windows.storage.streams as streams
import winsdk.windows.graphics.imaging as imaging

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

HWND = 329612
PLACEMENT = None


class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [("length", wintypes.UINT), ("flags", wintypes.UINT), ("showCmd", wintypes.UINT),
                ("ptMinPosition", wintypes.POINT), ("ptMaxPosition", wintypes.POINT),
                ("rcNormalPosition", wintypes.RECT)]


wp = WINDOWPLACEMENT()
wp.length = ctypes.sizeof(WINDOWPLACEMENT)
user32.GetWindowPlacement(HWND, ctypes.byref(wp))
print("showCmd:", wp.showCmd, "normal:", wp.rcNormalPosition.left, wp.rcNormalPosition.top,
      wp.rcNormalPosition.right, wp.rcNormalPosition.bottom)

# SW_SHOWNOACTIVATE = 4 -> shows without activating; keeps window state sane
user32.ShowWindow(HWND, 4)
time.sleep(0.6)
r = wintypes.RECT()
user32.GetWindowRect(HWND, ctypes.byref(r))
print("rect after show:", r.left, r.top, r.right, r.bottom)
w, h = r.right - r.left, r.bottom - r.top

hwnd_dc = user32.GetWindowDC(HWND)
mfc = gdi32.CreateCompatibleDC(hwnd_dc)
bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
gdi32.SelectObject(mfc, bmp)
print("PrintWindow:", user32.PrintWindow(HWND, mfc, 2))


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BI(ctypes.Structure):
    _fields_ = [("bmiHeader", BIH), ("bmiColors", wintypes.DWORD * 3)]


bi = BI()
bi.bmiHeader.biSize = ctypes.sizeof(BIH)
bi.bmiHeader.biWidth = w
bi.bmiHeader.biHeight = -h
bi.bmiHeader.biPlanes = 1
bi.bmiHeader.biBitCount = 32
buf = ctypes.create_string_buffer(w * h * 4)
gdi32.GetDIBits(mfc, bmp, 0, h, buf, ctypes.byref(bi), 0)
img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
img.save("shot_chatlist.png")
print("saved", img.size, "colors:", len(img.getcolors(2000000) or []))
gdi32.DeleteObject(bmp)
gdi32.DeleteDC(mfc)
user32.ReleaseDC(HWND)

# restore previous state
user32.ShowWindow(HWND, 6 if wp.showCmd == 2 else 0)
print("restored showCmd", wp.showCmd)


async def do_ocr(path):
    eng = None
    for l in ocr.OcrEngine.available_recognizer_languages:
        if l.language_tag.lower().startswith("zh"):
            eng = ocr.OcrEngine.try_create_from_language(l)
            break
    with open(path, "rb") as f:
        data = f.read()
    s = streams.InMemoryRandomAccessStream()
    wr = streams.DataWriter(s)
    wr.write_bytes(data)
    await wr.store_async()
    await wr.flush_async()
    wr.detach_stream()
    s.seek(0)
    dec = await imaging.BitmapDecoder.create_async(s)
    sb = await dec.get_software_bitmap_async()
    res = await eng.recognize_async(sb)
    print("--- OCR ---")
    for line in res.lines:
        r0 = line.words[0].bounding_rect
        print(f"y={r0.y:6.0f} x={r0.x:6.0f}  {line.text!r}")


asyncio.run(do_ocr("shot_chatlist.png"))
