"""Check Windows built-in OCR languages and test OCR on a PrintWindow capture of WeChat."""
import asyncio
import ctypes
from ctypes import wintypes
import io

from PIL import Image
import winsdk.windows.media.ocr as ocr
import winsdk.windows.globalization as glob
import winsdk.windows.storage.streams as streams
import winsdk.windows.graphics.imaging as imaging


user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)


def capture_hwnd(hwnd: int, path: str):
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w <= 0 or h <= 0:
        raise RuntimeError(f"bad rect {w}x{h}")
    hwnd_dc = user32.GetWindowDC(hwnd)
    mfc_dc = gdi32.CreateCompatibleDC(hwnd_dc)
    bmp = gdi32.CreateCompatibleBitmap(hwnd_dc, w, h)
    gdi32.SelectObject(mfc_dc, bmp)
    # PW_RENDERFULLCONTENT = 2
    ok = user32.PrintWindow(hwnd, mfc_dc, 2)
    print("PrintWindow ok:", ok)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                    ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    lines = gdi32.GetDIBits(mfc_dc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    print("GetDIBits lines:", lines)
    img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    img.save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mfc_dc)
    user32.ReleaseDC(hwnd)

    # detect blank capture (all black) for diagnosis
    colors = img.getcolors(maxcolors=1000000)
    print("distinct colors:", len(colors) if colors else ">1M")
    if colors:
        colors.sort(reverse=True)
        print("top colors:", colors[:3])
    return img


async def ocr_image(path: str):
    try:
        langs = ocr.OcrEngine.available_recognizer_languages
    except AttributeError:
        langs = ocr.OcrEngine.get_available_recognizer_languages()
    print("OCR languages:", [(l.language_tag, l.display_name) for l in langs])
    engine = None
    for l in langs:
        if l.language_tag.lower().startswith("zh"):
            engine = ocr.OcrEngine.try_create_from_language(l)
            break
    if engine is None:
        engine = ocr.OcrEngine.try_create_from_user_profile_languages()
    print("engine:", engine, "lang:", engine.recognizer_language.language_tag if engine else None)
    if engine is None:
        return
    with open(path, "rb") as f:
        data = f.read()
    stream = streams.InMemoryRandomAccessStream()
    writer = streams.DataWriter(stream)
    writer.write_bytes(data)
    await writer.store_async()
    await writer.flush_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await imaging.BitmapDecoder.create_async(stream)
    bmp = await decoder.get_software_bitmap_async()
    result = await engine.recognize_async(bmp)
    print("--- OCR TEXT ---")
    for line in result.lines:
        print(repr(line.text), [(w.bounding_rect.x, w.bounding_rect.y, w.bounding_rect.width, w.bounding_rect.height) for w in line.words][:2])


if __name__ == "__main__":
    hwnd = 329612
    img = capture_hwnd(hwnd, "shot_main.png")
    print("saved shot_main.png", img.size)
    asyncio.run(ocr_image("shot_main.png"))
