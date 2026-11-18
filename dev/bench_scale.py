"""Compare RapidOCR speed/accuracy at different upscales on the chat list."""
import time
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

engine = RapidOCR()
img = Image.open("shot_covered.png").convert("RGB")
base = img.crop((66, 70, 302, 641))

for scale in (1.0, 1.25, 1.5, 2.0):
    im = base.resize((int(base.width * scale), int(base.height * scale)), Image.LANCZOS)
    p = f"scale_{scale}.png"
    im.save(p)
    t0 = time.time()
    res, _ = engine(p)
    dt = time.time() - t0
    print(f"--- scale {scale}: {dt:.2f}s, {len(res or [])} lines")
    for box, text, score in (res or [])[:6]:
        print(f"   {text} ({score:.2f})")
