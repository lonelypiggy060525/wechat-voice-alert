"""Full-screen change detector: saves frames whenever the screen changes, for N seconds."""
import os
import sys
import time

import numpy as np
from PIL import ImageGrab

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 90
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frames")
os.makedirs(OUT, exist_ok=True)

prev = None
t0 = time.time()
saved = 0
last_save = 0.0
while time.time() - t0 < DURATION:
    img = ImageGrab.grab(all_screens=True)
    small = np.asarray(img.convert("L").resize((480, 270)), dtype=np.int16)
    if prev is not None:
        d = np.abs(small - prev)
        frac = float((d > 14).mean())
        if frac > 0.002 and (time.time() - last_save) > 0.35:
            ts = time.strftime("%H%M%S", time.localtime())
            ms = int((time.time() % 1) * 1000)
            path = os.path.join(OUT, f"f_{ts}_{ms:03d}.png")
            img.save(path)
            print(f"{path} change={frac:.4f}", flush=True)
            saved += 1
            last_save = time.time()
    prev = small
    time.sleep(0.15)

print("done, frames:", saved)
