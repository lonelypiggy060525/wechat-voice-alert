"""Generate assets/icon.ico (same look as the tray icon)."""
import os

from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")


def make(size: int) -> Image.Image:
    s = size * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = max(1, int(s * 0.045))
    d.rounded_rectangle((pad, pad, s - pad, s - pad), radius=int(s * 0.24), fill=(7, 193, 96, 255))
    bw, bh = int(s * 0.52), int(s * 0.36)
    bx = (s - bw) // 2
    by = int(s * 0.30)
    d.rounded_rectangle((bx, by, bx + bw, by + bh), radius=int(s * 0.09), fill=(255, 255, 255, 255))
    tail = [(bx + int(bw * 0.22), by + bh - int(s * 0.02)),
            (bx + int(bw * 0.22), by + bh + int(s * 0.10)),
            (bx + int(bw * 0.46), by + bh - int(s * 0.04))]
    d.polygon(tail, fill=(255, 255, 255, 255))
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    sizes = [256, 128, 64, 48, 32, 16]
    imgs = [make(s) for s in sizes]
    imgs[0].save(OUT, format="ICO", sizes=[(s, s) for s in sizes])
    print("wrote", OUT, os.path.getsize(OUT), "bytes")
