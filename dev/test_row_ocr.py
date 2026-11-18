"""OCR a single chat row at 3x to check readability."""
from PIL import Image, ImageEnhance
from winocr import ocr_image

img = Image.open("shot_covered.png").convert("RGB")

rows = {"那只猪猪": 466, "极乐净土": 202, "小猪饲养员": 326, "两只一只": 388}
for name, top in rows.items():
    crop = img.crop((130, top, 302, top + 60))
    for scale in (2, 3, 4):
        up = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
        up = ImageEnhance.Contrast(up).enhance(1.25)
        lines = ocr_image(up)
        txt = " | ".join(f"{ln['text']}@y{ln['y']//scale}" for ln in lines)
        print(f"{name} x{scale}: {txt}")
    print()
