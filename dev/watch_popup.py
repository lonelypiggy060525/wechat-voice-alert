"""Watch for WeChat notification popup windows for N seconds, capture + OCR them."""
import asyncio
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

from PIL import Image, ImageGrab
import winsdk.windows.media.ocr as ocr
import winsdk.windows.storage.streams as streams
import winsdk.windows.graphics.imaging as imaging

OUT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(OUT, "capture_log.jsonl")
DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 300

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


def weixin_pids():
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True).stdout.decode("gbk", "replace")
    pids = set()
    for line in out.splitlines():
        parts = [p.strip('\"') for p in line.split('\",\"')]
        if parts and parts[0].lower() in ("weixin.exe", "wechatappex.exe"):
            pids.add(int(parts[1]))
    return pids


def enum_windows(pids):
    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    res = []

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
        res.append({
            "hwnd": hwnd, "pid": pid.value, "cls": cls.value, "title": title.value,
            "rect": [r.left, r.top, r.right, r.bottom],
            "visible": bool(user32.IsWindowVisible(hwnd)),
        })
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return res


def capture_hwnd(hwnd, path):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        return None
    hwnd_dc = user32.GetWindowDC(hwnd)
    mfc_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mfc_dc, bmp)
    user32.PrintWindow(hwnd, mfc_dc, 2)

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
    gdi32.GetDIBits(mfc_dc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    img.save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mfc_dc)
    user32.ReleaseDC(hwnd)
    return img


ENGINE = None


def get_engine():
    global ENGINE
    if ENGINE is not None:
        return ENGINE
    for l in ocr.OcrEngine.available_recognizer_languages:
        if l.language_tag.lower().startswith("zh"):
            ENGINE = ocr.OcrEngine.try_create_from_language(l)
            break
    if ENGINE is None:
        ENGINE = ocr.OcrEngine.try_create_from_user_profile_languages()
    return ENGINE


async def ocr_img(img: Image.Image):
    engine = get_engine()
    if engine is None:
        return []
    import io
    b = io.BytesIO()
    img.save(b, "PNG")
    stream = streams.InMemoryRandomAccessStream()
    writer = streams.DataWriter(stream)
    writer.write_bytes(b.getvalue())
    await writer.store_async()
    await writer.flush_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await imaging.BitmapDecoder.create_async(stream)
    sbmp = await decoder.get_software_bitmap_async()
    res = await engine.recognize_async(sbmp)
    return [line.text for line in res.lines]


def log(obj):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(json.dumps(obj, ensure_ascii=False))


async def main():
    pids = weixin_pids()
    seen = {w["hwnd"] for w in enum_windows(pids)}
    log({"event": "start", "pids": sorted(pids), "baseline": sorted(seen)})
    t0 = time.time()
    n = 0
    while time.time() - t0 < DURATION:
        pids = weixin_pids()
        wins = enum_windows(pids)
        for w in wins:
            if w["hwnd"] in seen:
                continue
            seen.add(w["hwnd"])
            n += 1
            if w["rect"][2] - w["rect"][0] < 20:
                continue
            w["event"] = "new_window"
            w["t"] = round(time.time(), 3)
            log(w)
            await asyncio.sleep(0.25)
            tag = f"win{n}_{w['hwnd']}"
            try:
                img = capture_hwnd(w["hwnd"], os.path.join(OUT, f"{tag}.png"))
                if img:
                    w["printwindow_size"] = img.size
                    w["printwindow_ocr"] = await ocr_img(img)
            except Exception as e:
                w["capture_err"] = repr(e)
            try:
                l, t, r, b = w["rect"]
                full = ImageGrab.grab(bbox=(max(l - 4, 0), max(t - 4, 0), r + 4, b + 4), all_screens=True)
                full.save(os.path.join(OUT, f"{tag}_screen.png"))
                w["screen_ocr"] = await ocr_img(full)
            except Exception as e:
                w["screen_err"] = repr(e)
            log({"event": "capture", **w})
        for w in wins:
            if w["hwnd"] in seen and w["visible"] and w["cls"] not in ("Qt51514QWindowIcon",) and w["rect"][2] - w["rect"][0] > 60 and w["hwnd"] not in getattr(main, "reported", set()):
                pass
        await asyncio.sleep(0.1)
    log({"event": "end", "new_windows": n})


asyncio.run(main())
