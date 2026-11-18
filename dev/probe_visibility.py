"""Watch Weixin windows' visibility + notification center for N seconds; log every change."""
import asyncio
import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes

from winsdk.windows.ui.notifications import NotificationKinds
from winsdk.windows.ui.notifications.management import UserNotificationListener

DURATION = int(sys.argv[1]) if len(sys.argv) > 1 else 180
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "visibility_log.jsonl")
user32 = ctypes.WinDLL("user32", use_last_error=True)
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def pids():
    out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True).stdout.decode("gbk", "replace")
    s = set()
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if parts and parts[0].lower() in ("weixin.exe", "wechatappex.exe"):
            s.add(int(parts[1]))
    return s


def snapshot():
    ps = pids()
    res = {}

    def cb(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in ps:
            return True
        cls = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls, 256)
        n = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(n + 1)
        user32.GetWindowTextW(hwnd, title, n + 1)
        r = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r))
        res[hwnd] = {"cls": cls.value, "title": title.value, "vis": bool(user32.IsWindowVisible(hwnd)),
                     "rect": [r.left, r.top, r.right, r.bottom]}
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return res


def log(o):
    o["t"] = time.strftime("%H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(o, ensure_ascii=False) + "\n")
    print(json.dumps(o, ensure_ascii=False), flush=True)


async def main():
    listener = UserNotificationListener.current
    base = snapshot()
    log({"event": "start", "windows": {str(k): v for k, v in base.items()}})
    seen_notif = set()
    t0 = time.time()
    while time.time() - t0 < DURATION:
        cur = snapshot()
        for hwnd, info in cur.items():
            old = base.get(hwnd)
            if old is None:
                log({"event": "window_new", "hwnd": hwnd, **info})
            elif old["vis"] != info["vis"] or old["rect"] != info["rect"]:
                log({"event": "window_change", "hwnd": hwnd, "from": old, "to": info})
        for hwnd in set(base) - set(cur):
            log({"event": "window_gone", "hwnd": hwnd})
        base = cur
        try:
            notifs = await listener.get_notifications_async(NotificationKinds.TOAST)
            for n in notifs:
                key = int(n.id)
                if key in seen_notif:
                    continue
                seen_notif.add(key)
                texts = []
                try:
                    b = n.notification.visual.get_binding("ToastGeneric")
                    texts = [e.text for e in b.get_text_elements()] if b else []
                except Exception:
                    pass
                log({"event": "toast", "app": n.app_info.display_info.display_name,
                     "aumid": n.app_info.app_user_model_id, "texts": texts})
        except Exception as e:
            log({"event": "toast_err", "err": repr(e)})
        await asyncio.sleep(0.25)
    log({"event": "end"})


asyncio.run(main())
