"""One-shot debug: capture WeChat, OCR chat list, show parsed rows and badges."""
import ctypes
import wechat_list as wl

hwnd = wl.find_wechat_window()
print("hwnd:", hwnd, "minimized:", bool(ctypes.windll.user32.IsIconic(hwnd)) if hwnd else None)
img = wl.capture_window(hwnd)
print("capture:", img.size if img else None)
badges = wl.badge_rows(img)
print("badge rows (y0,y1):", badges)
lines = wl.ChatListWatcher(lambda m: None, lambda s: None)._ocr(img)
print("ocr lines:", len(lines))
for ln in lines[:30]:
    print(f"  y={ln['y']:4d} x={ln['x']:4d} {ln['text']!r}")
rows = wl.group_rows(lines)
print("\nparsed rows:")
for row in rows:
    marked = any(y0 - 6 <= (y0 + y1) / 2 <= row["y"] + 46 for y0, y1 in badges) if badges else False
    print(f"  y={row['y']:4d} {'[未读]' if marked else '      '} {row['name']!r}  <- {row['preview']!r}")
