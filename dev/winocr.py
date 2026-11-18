"""Windows built-in OCR (Windows.Media.Ocr) helper: PIL image -> lines with positions."""
from __future__ import annotations

import asyncio
import io
from typing import List, TypedDict

import winsdk.windows.graphics.imaging as imaging
import winsdk.windows.media.ocr as ocr
import winsdk.windows.storage.streams as streams
from PIL import Image


class Line(TypedDict):
    text: str
    x: int
    y: int
    w: int
    h: int


_engine = None
_engine_lock = asyncio.Lock() if False else None


def get_engine(lang_prefix: str = "zh"):
    global _engine
    if _engine is not None:
        return _engine
    langs = ocr.OcrEngine.available_recognizer_languages
    for lang in langs:
        if lang.language_tag.lower().startswith(lang_prefix):
            _engine = ocr.OcrEngine.try_create_from_language(lang)
            break
    if _engine is None and langs:
        _engine = ocr.OcrEngine.try_create_from_language(langs[0])
    if _engine is None:
        _engine = ocr.OcrEngine.try_create_from_user_profile_languages()
    return _engine


async def _ocr_async(image: Image.Image, lang_prefix: str = "zh") -> List[Line]:
    engine = get_engine(lang_prefix)
    if engine is None:
        return []
    buf = io.BytesIO()
    image.convert("RGB").save(buf, "PNG")
    stream = streams.InMemoryRandomAccessStream()
    writer = streams.DataWriter(stream)
    writer.write_bytes(buf.getvalue())
    await writer.store_async()
    await writer.flush_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await imaging.BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    result = await engine.recognize_async(bitmap)
    out: List[Line] = []
    for line in result.lines:
        words = list(line.words)
        if not words:
            continue
        r = words[0].bounding_rect
        x0 = min(w.bounding_rect.x for w in words)
        y0 = min(w.bounding_rect.y for w in words)
        x1 = max(w.bounding_rect.x + w.bounding_rect.width for w in words)
        y1 = max(w.bounding_rect.y + w.bounding_rect.height for w in words)
        out.append({"text": line.text, "x": int(x0), "y": int(y0), "w": int(x1 - x0), "h": int(y1 - y0)})
    return out


def ocr_image(image: Image.Image, lang_prefix: str = "zh") -> List[Line]:
    """Synchronous OCR. Safe to call from worker threads (each call owns its own loop)."""
    return asyncio.run(_ocr_async(image, lang_prefix))


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "shot_chatlist.png"
    for ln in ocr_image(Image.open(path)):
        print(f"y={ln['y']:4d} x={ln['x']:4d} {ln['text']!r}")
