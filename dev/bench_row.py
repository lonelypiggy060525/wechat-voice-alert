"""Benchmark RapidOCR on a single chat row crop."""
import time
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

engine = RapidOCR()
img = Image.open("shot_covered.png").convert("RGB")

rows = {"那只猪猪": 466, "极乐净土": 202, "小猪饲养员": 326, "公众号": 466 + 62}
for name, top in rows.items():
    crop = img.crop((132, top - 2, 302, top + 50))
    crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
    p = f"row_{abs(hash(name)) % 1000}.png"
    crop.save(p)
    t0 = time.time()
    res, _ = engine(p)
    dt = time.time() - t0
    texts = [(min(pt[1] for pt in box) / 2, text, round(score, 2)) for box, text, score in (res or [])]
    print(f"{name}: {dt*1000:.0f}ms -> {texts}")
