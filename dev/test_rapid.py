"""Compare RapidOCR on full chat list vs row crops."""
import time
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

engine = RapidOCR()
img = Image.open("shot_covered.png").convert("RGB")
list_img = img.crop((66, 70, 302, 641))
list_img = list_img.resize((list_img.width * 2, list_img.height * 2), Image.LANCZOS)
list_img.save("list_crop.png")

t0 = time.time()
result, elapse = engine("list_crop.png")
print(f"full list OCR: {time.time()-t0:.2f}s, {len(result) if result else 0} boxes")
for box, text, score in (result or []):
    ys = [p[1] for p in box] / 2 if False else [p[1] for p in box]
    xs = [p[0] for p in box]
    print(f"  y={min(ys)/2:5.0f} x={min(xs)/2:4.0f} score={score:.2f} {text}")
