"""Watch every new top-level window (all processes) + screen changes for N seconds."""
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

from PIL import ImageGrab
import numpy as np

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 90
OUT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(OUT, "live_log.jsonl")
FRAMES = os.path.join(OUT, "frames")
os.makedirs(FRAMES, exist_ok=True)

user32 = ctypes.WinDLL("user32", use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def enum_all():
    res = []

    def cb(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        n = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, title, n + 1)
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        res.append((hwnd, pid.value, cls.value, title.value, r.left, r.top, r.right, r.bottom,
                    bool(user32.IsWindowVisible(hwnd))))
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return res


def log(obj):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


base = {w[0] for w in enum_all()}
log({"event": "start", "time": time.strftime("%H:%M:%S"), "windows": len(base)})
print("watching", len(base), "windows for", DURATION, "s", flush=True)

prev = None
t0 = time.time()
last_save = 0
while time.time() - t0 < DURATION:
    for w in enum_all():
        if w[0] in base:
            continue
        base.add(w[0])
        if w[6] - w[4] < 10 or w[7] - w[5] < 10:
            continue
        item = {"event": "new_window", "hwnd": w[0], "pid": w[1], "cls": w[2], "title": w[3],
                "rect": [w[4], w[5], w[6], w[7]], "visible": w[8], "t": time.strftime("%H:%M:%S")}
        log(item)
        print("NEW", item, flush=True)
        try:
            img = ImageGrab.grab(bbox=(w[4], w[5], w[6], w[7]), all_screens=True)
            img.save(os.path.join(FRAMES, f"w_{w[0]}.png"))
        except Exception as e:
            item["cap_err"] = repr(e)

    img = ImageGrab.grab(all_screens=True)
    small = np.asarray(img.convert("L").resize((480, 270)), dtype=np.int16)
    if prev is not None:
        frac = float((np.abs(small - prev) > 14).mean())
        if frac > 0.0015 and time.time() - last_save > 0.4:
            p = os.path.join(FRAMES, f"s_{int(time.time()*1000)}.png")
            img.save(p)
            log({"event": "screen_change", "frac": round(frac, 4), "file": os.path.basename(p),
                 "t": time.strftime("%H:%M:%S")})
            print("CHANGE", round(frac, 4), p, flush=True)
            last_save = time.time()
    prev = small
    time.sleep(0.18)
log({"event": "end"})
print("done", flush=True)
