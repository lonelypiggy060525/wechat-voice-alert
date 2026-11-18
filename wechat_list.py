"""Read WeChat's chat list from the screen (WeChat 4.x exposes no UIA tree and no toasts).

Cheap red-badge scan every poll decides *whether* something happened; the expensive
OCR only runs when the avatar column changes. Only rows with an unread badge are
announced, so messages you send yourself never trigger it.
"""
from __future__ import annotations

import ctypes
import re
import threading
import time
from ctypes import wintypes
from typing import Callable

import numpy as np
from PIL import Image

from notif_watcher import _looks_like_sender

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

WECHAT_CLASSES = ("Qt51514QWindowIcon",)
WECHAT_TITLES = ("微信", "Weixin")

HWND_BOTTOM = 1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_NOOWNERZORDER = 0x0200

# geometry of WeChat 4.2's left panel, in window pixels at 100% scaling
LIST_LEFT = 66
LIST_RIGHT = 302
AVATAR_LEFT = 84
AVATAR_RIGHT = 130
ROW_GAP = 28          # y distance that separates two rows in OCR output

_TIME_RE = re.compile(
    r"\s*(?:昨天|前天|星期[一二三四五六日]|周[一二三四五六日])?\s*(?:上午|下午|凌晨|晚上)?\s*"
    r"\d{1,2}[:：]\d{2}\s*$|"
    r"\s*(?:昨天|前天|星期[一二三四五六日]|周[一二三四五六日])\s*\d{1,2}[:：]\d{2}\s*$|"
    r"\s*\d{1,2}\s*[/月]\s*\d{1,2}\s*日?\s*$"
)
_TRAIL_DOTS = re.compile(r"[.．·…]{1,4}$")
_NAME_OK = re.compile(r"[A-Za-z\u4e00-\u9fa5]")
_PLACEHOLDER_WORDS = ("表情", "图片", "动画", "视频", "语音", "文件", "链接", "位置", "名片", "红包", "转账", "聊天记录", "小程序")


class BIH(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]


class BI(ctypes.Structure):
    _fields_ = [("bmiHeader", BIH), ("bmiColors", wintypes.DWORD * 3)]


def show_in_background(hwnd: int) -> None:
    """Restore a minimized/tray-hidden window without stealing focus **and** sink it
    to the bottom of the z-order - SW_SHOWNOACTIVATE alone would pop it to the front."""
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 4)   # SW_SHOWNOACTIVATE restores without activating
    user32.SetWindowPos(hwnd, HWND_BOTTOM, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER | SWP_SHOWWINDOW)


SWP_NOZORDER = 0x0004
SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN, SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN = 76, 77, 78, 79
CONV_LEFT, CONV_TOP = 312, 55          # conversation pane starts right of the chat list

_TIME_ONLY = re.compile(
    r"^(?:(?:昨天|今天|前天|星期[一二三四五六日天]|周[一二三四五六日天]|"
    r"\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}[日号])?\s*\d{1,2}[:：]\d{2}"
    r"|昨天|今天|前天|星期[一二三四五六日天]|\d{4}年\d{1,2}月\d{1,2}日)$")


def is_time_line(text: str) -> bool:
    return bool(_TIME_ONLY.match(text.strip()))


def click_chat_row(hwnd: int, y: int, x: int = 180) -> None:
    """Select a chat row without moving the mouse or focusing the window."""
    lp = ((y & 0xFFFF) << 16) | (x & 0xFFFF)
    user32.PostMessageW(hwnd, 0x0201, 0x0001, lp)     # WM_LBUTTONDOWN
    time.sleep(0.04)
    user32.PostMessageW(hwnd, 0x0202, 0, lp)          # WM_LBUTTONUP


def ocr_region(engine, img, box: tuple[int, int, int, int]) -> list[dict]:
    """OCR an arbitrary region; coordinates come back in full-image space."""
    crop = img.crop(box)
    crop = crop.resize((int(crop.width * 1.5), int(crop.height * 1.5)), Image.LANCZOS)
    result, _ = engine(np.asarray(crop), use_cls=False)
    lines = []
    for item in (result or []):
        box_pts, text, score = item
        if score < 0.5:
            continue
        xs = [p[0] / 1.5 for p in box_pts]
        ys = [p[1] / 1.5 for p in box_pts]
        lines.append({"text": text, "x": int(min(xs)) + box[0], "y": int(min(ys)) + box[1],
                      "w": int(max(xs) - min(xs))})
    return lines


def _wants_full(content: str, preview_w: int = 0) -> bool:
    """True when the list preview was trimmed: its rendered width fills the column."""
    text = (content or "").strip()
    if not text or text.startswith("["):
        return False
    return preview_w >= 150 or len(text) >= 18


def _same_chat(header: str, name: str) -> bool:
    """Compare an OCR'd conversation header with a chat-list name, tolerating OCR noise."""
    def norm(s: str) -> str:
        return re.sub(r"[\s\W_]+", "", s or "")

    head, target = norm(header), norm(name)
    if not head or not target:
        return False
    return head.startswith(target) or target.startswith(head) or target in head


def parse_last_bubble(lines: list[dict], width: int) -> str:
    """Reassemble the newest incoming bubble from OCR lines of the conversation pane.
    Drops timestamps and my own right-aligned messages."""
    keep = [l for l in lines
            if l["x"] < width * 0.62 and not is_time_line(l["text"]) and l["text"].strip()]
    if not keep:
        return ""
    keep.sort(key=lambda l: (l["y"], l["x"]))
    block = [keep[-1]]
    for line in reversed(keep[:-1]):
        if block[0]["y"] - line["y"] <= 24 and abs(line["x"] - keep[-1]["x"]) <= 16:
            block.insert(0, line)
        else:
            break
    text = "".join(l["text"].strip() for l in block)
    return text.strip()


def virtual_bounds() -> tuple[int, int, int, int]:
    u = user32
    return (u.GetSystemMetrics(SM_XVIRTUALSCREEN), u.GetSystemMetrics(SM_YVIRTUALSCREEN),
            u.GetSystemMetrics(SM_CXVIRTUALSCREEN), u.GetSystemMetrics(SM_CYVIRTUALSCREEN))


def window_rect(hwnd: int) -> tuple[int, int, int, int]:
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return int(r.left), int(r.top), int(r.right), int(r.bottom)


def is_on_screen(hwnd: int) -> bool:
    """True when any part of the window overlaps the virtual desktop."""
    l, t, rgt, b = window_rect(hwnd)
    vx, vy, vw, vh = virtual_bounds()
    return not (rgt <= vx or l >= vx + vw or b <= vy or t >= vy + vh)


def park_offscreen(hwnd: int) -> bool:
    """Move the window just outside the virtual desktop: invisible to the user,
    still composed, so PrintWindow keeps working."""
    l, t, rgt, b = window_rect(hwnd)
    vx, _vy, _vw, _vh = virtual_bounds()
    width = rgt - l
    if width <= 0:
        return False
    if rgt <= vx:          # already parked
        return True
    x = vx - width - 80
    return bool(user32.SetWindowPos(hwnd, 0, x, t, 0, 0,
                                    SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER))


def bring_on_screen(hwnd: int) -> bool:
    """Put the window back in the middle of the primary monitor (no focus steal)."""
    l, t, rgt, b = window_rect(hwnd)
    w, h = rgt - l, b - t
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    x = max(0, (sw - w) // 2)
    y = max(0, (sh - h) // 3)
    return bool(user32.SetWindowPos(hwnd, 0, x, y, 0, 0,
                                    SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_NOOWNERZORDER))


def find_wechat_window() -> int | None:
    for cls in WECHAT_CLASSES:
        for title in WECHAT_TITLES:
            hwnd = user32.FindWindowW(cls, title)
            if hwnd:
                return hwnd
    return None


def capture_window(hwnd: int) -> Image.Image | None:
    r = wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    w, h = r.right - r.left, r.bottom - r.top
    if w < 400 or h < 300:
        return None
    dc = user32.GetWindowDC(hwnd)
    if not dc:
        return None
    mdc = gdi32.CreateCompatibleDC(dc)
    bmp = gdi32.CreateCompatibleBitmap(dc, w, h)
    gdi32.SelectObject(mdc, bmp)
    ok = user32.PrintWindow(hwnd, mdc, 2)
    bi = BI()
    bi.bmiHeader.biSize = ctypes.sizeof(BIH)
    bi.bmiHeader.biWidth = w
    bi.bmiHeader.biHeight = -h
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    img = None
    if ok:
        img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(hwnd, dc)
    return img


def badge_mask(img: Image.Image) -> np.ndarray:
    """Boolean mask of WeChat's unread badge red inside the avatar column."""
    a = np.asarray(img.convert("RGB")).astype(np.int16)
    band = a[:, AVATAR_LEFT:AVATAR_RIGHT, :]
    r, g, b = band[:, :, 0], band[:, :, 1], band[:, :, 2]
    return (r > 165) & (g < 115) & (b < 115) & ((r - g) > 85)


def badge_rows(img: Image.Image) -> list[tuple[int, int]]:
    """Return [(y_top, y_bottom)] for each badge blob (deduped by row)."""
    m = badge_mask(img)
    ys, xs = np.nonzero(m)
    if len(ys) == 0:
        return []
    rows: list[list[int]] = []
    order = np.argsort(ys)
    ys_s, xs_s = ys[order], xs[order]
    start = 0
    for i in range(1, len(ys_s) + 1):
        if i == len(ys_s) or ys_s[i] - ys_s[i - 1] > 4:
            n = i - start
            if n >= 55:  # a badge digit has ~80-300 red pixels; a stray avatar pixel does not
                y0, y1 = int(ys_s[start]), int(ys_s[start:i - 1].max())
                x0, x1 = int(xs_s[start:i].min()), int(xs_s[start:i].max())
                if 10 <= (y1 - y0 + 1) <= 26 and 10 <= (x1 - x0 + 1) <= 30:
                    rows.append([y0, y1])
            start = i
    # merge blobs on the same row
    merged: list[list[int]] = []
    for y0, y1 in sorted(rows):
        if merged and y0 - merged[-1][1] < 12:
            merged[-1][1] = max(merged[-1][1], y1)
        else:
            merged.append([y0, y1])
    return [(a_, b_) for a_, b_ in merged]


def strip_signature(m: np.ndarray) -> int:
    packed = np.packbits(m)
    return hash(packed.tobytes())


def list_signature(img: Image.Image) -> int:
    """Cheap fingerprint of the whole chat list: any text/badge change flips it."""
    crop = img.crop((LIST_LEFT, 60, LIST_RIGHT, img.height)).convert("L").resize((56, 140))
    a = np.asarray(crop, dtype=np.int16) // 40
    return hash(a.astype(np.uint8).tobytes())


def clean_line(text: str) -> str:
    text = text.strip()
    text = _TIME_RE.sub("", text).strip()
    text = _TRAIL_DOTS.sub("", text).strip()
    return text


def group_rows(lines: list[dict]) -> list[dict]:
    """Turn OCR lines (text + y + x) into rows: name / preview / has_time."""
    rows: list[dict] = []
    for ln in sorted(lines, key=lambda d: (d["y"], d["x"])):
        if rows and ln["y"] - rows[-1]["last_y"] <= ROW_GAP:
            rows[-1]["lines"].append(ln)
            rows[-1]["last_y"] = max(rows[-1]["last_y"], ln["y"])
        else:
            rows.append({"lines": [ln], "y": ln["y"], "last_y": ln["y"]})
    out = []
    for row in rows:
        parts = []
        for ln in row["lines"]:
            txt = clean_line(ln["text"])
            if not txt:
                continue
            parts.append((ln["x"], txt, ln["y"], ln.get("w", 0)))
        if not parts:
            continue
        parts.sort(key=lambda p: (p[2], p[0]))
        badge = None
        if len(parts) > 1 and parts[0][0] < 57 and re.fullmatch(r"\d{1,3}\+?", parts[0][1]):
            # the unread counter was OCR'd as its own line above the name
            badge = parts[0][1]
            parts = parts[1:]
        name = parts[0][1]
        # OCR sometimes puts a stray number above the real name; skip such lines
        while parts and not _NAME_OK.search(parts[0][1]) and len(parts) > 1:
            parts = parts[1:]
            name = parts[0][1]
        if not _NAME_OK.search(name):
            continue
        preview = ""
        preview_w = 0
        for x, txt, y, w in parts[1:]:
            if x < 150:  # right-aligned timestamps live past x=150
                preview = txt  # keep the bottom-most line: that's the message preview
                preview_w = w
        out.append({"y": parts[0][2], "name": name, "preview": preview, "badge": badge,
                    "preview_w": preview_w})
    return out


class ChatListWatcher(threading.Thread):
    def __init__(self, on_message: Callable[[dict], None], on_status: Callable[[str], None],
                 interval: float = 0.8, auto_restore: Callable[[], bool] | None = None,
                 stealth: Callable[[], bool] | None = None,
                 full_read: Callable[[], bool] | None = None) -> None:
        super().__init__(name="chatlist-watcher", daemon=True)
        self.on_message = on_message
        self.on_status = on_status
        self.interval = interval
        self.auto_restore = auto_restore or (lambda: False)
        self.stealth = stealth or (lambda: False)
        self.full_read = full_read or (lambda: False)
        self._stealth_applied = False
        self._stop = threading.Event()
        self._engine = None
        self._prev: dict[str, tuple] = {}
        self._last_sig: int | None = None
        self._last_ocr = 0.0
        self._status = ""

    def stop(self) -> None:
        self._stop.set()

    def _set_status(self, text: str) -> None:
        if text != self._status:
            self._status = text
            self.on_status(text)

    def _get_engine(self):
        if self._engine is None:
            from rapidocr_onnxruntime import RapidOCR
            # 2 threads: ~0.85 s per list instead of 0.6 s, but half the CPU burst
            self._engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
        return self._engine

    def _ocr(self, img: Image.Image) -> list[dict]:
        crop = img.crop((LIST_LEFT, 60, LIST_RIGHT, img.height))
        crop = crop.resize((int(crop.width * 1.5), int(crop.height * 1.5)), Image.LANCZOS)
        engine = self._get_engine()
        result, _ = engine(np.asarray(crop), use_cls=False)
        lines = []
        for box, text, score in (result or []):
            if score < 0.5:
                continue
            xs = [p[0] / 1.5 for p in box]
            ys = [p[1] / 1.5 for p in box]
            lines.append({"text": text, "x": int(min(xs)), "y": int(min(ys)) + 60,
                          "w": int(max(xs) - min(xs))})
        return lines

    def run(self) -> None:
        try:
            self._get_engine()
        except Exception as exc:
            self._set_status(f"OCR 引擎加载失败：{exc}")
            return
        seeded = False
        while not self._stop.is_set():
            hwnd = find_wechat_window()
            if not hwnd:
                self._set_status("等待微信登录")
                time.sleep(2)
                continue
            if user32.IsIconic(hwnd) or not user32.IsWindowVisible(hwnd):
                hidden = not user32.IsWindowVisible(hwnd)
                if self.auto_restore() or self.stealth():
                    # stealth implies "keep working": bring it back off-screen instead of leaving it dead
                    show_in_background(hwnd)
                    if self.stealth():
                        park_offscreen(hwnd)
                    time.sleep(0.8)
                    continue
                self._set_status("微信在托盘里/已最小化，勾选「自动还原」才能提醒" if hidden
                                 else "微信已最小化，勾选「自动还原」才能提醒")
                time.sleep(1.2)
                continue

            # stealth: park it once after start-up, never fight the user afterwards
            if self.stealth():
                if not self._stealth_applied and is_on_screen(hwnd):
                    park_offscreen(hwnd)
                self._stealth_applied = True
            else:
                self._stealth_applied = False
            img = capture_window(hwnd)
            if img is None:
                time.sleep(self.interval)
                continue
            mask = badge_mask(img)
            sig = list_signature(img)
            now = time.time()
            if sig == self._last_sig or now - self._last_ocr < 1.2:
                time.sleep(self.interval)
                continue
            self._last_sig = sig
            self._last_ocr = now
            try:
                lines = self._ocr(img)
            except Exception as exc:
                self._set_status(f"OCR 失败：{exc}")
                time.sleep(2)
                continue
            rows = group_rows(lines)
            badges = badge_rows(img)
            unread_rows = []
            for y0, y1 in badges:
                centre = (y0 + y1) / 2
                best = None
                for row in rows:
                    if row["y"] - 6 <= centre <= row["y"] + 46:
                        best = row
                        break
                if best is None:
                    continue
                unread_rows.append(best)
            if not unread_rows:
                self._set_status("运行中")
            else:
                self._set_status(f"运行中 · {len(unread_rows)} 条未读")

            clicked = False
            for row in unread_rows:
                name, preview, badge = row["name"], row["preview"], row.get("badge")
                if not name:
                    continue
                old = self._prev.get(name)          # (preview, badge) or None
                changed = old is None or old[0] != preview or (badge is not None and old[1] != badge)
                if seeded and changed and (preview or badge):
                    msg = self._make_message(name, preview)
                    if self.full_read() and _wants_full(msg["content"], row.get("preview_w", 0)):
                        full = self._read_full(hwnd, row)
                        if full:
                            msg["content"] = full
                            msg["full"] = True
                        clicked = True
                    self.on_message(msg)
                    self._prev[name] = (preview, badge)
                    if clicked:
                        # selecting a chat reorders the list - re-capture before touching rows again
                        break
                else:
                    self._prev[name] = (preview, badge)
            # remember rows that lost their badge, so the next unread is detected again
            if not clicked:
                for row in rows:
                    if row["preview"]:
                        self._prev.setdefault(row["name"], (row["preview"], row.get("badge")))
            else:
                self._last_sig = None
            seeded = True
            time.sleep(self.interval)

    def _read_full(self, hwnd: int, row: dict) -> str:
        """Open the chat (posted click, no focus change) and OCR the newest bubble.
        Waits until the conversation header actually shows that chat, so we never
        read the previous chat's text by accident."""
        name = row.get("name", "")
        if user32.GetForegroundWindow() == hwnd:
            return ""          # the user is reading WeChat right now - never yank the view
        click_chat_row(hwnd, int(row.get("y", 0)) + 20)
        deadline = time.time() + 3.5
        while time.time() < deadline:
            time.sleep(0.3)
            img = capture_window(hwnd)
            if img is None:
                continue
            head = self._ocr_header(img)
            if not _same_chat(head, name):
                continue
            lines = ocr_region(self._get_engine(), img,
                               (CONV_LEFT, CONV_TOP, img.width - 8, img.height - 95))
            text = parse_last_bubble(lines, img.width)
            if text:
                return text
        return ""

    def _ocr_header(self, img) -> str:
        crop = img.crop((CONV_LEFT, 42, min(img.width, 780), 88))
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
        result, _ = self._get_engine()(np.asarray(crop), use_cls=False)
        return " ".join(text for _box, text, _score in (result or []))

    @staticmethod
    def _make_message(name: str, preview: str) -> dict:
        sender, content = name, preview
        m = re.match(r"^(.{1,20}?)[：:]\s*(\S.*)$", preview, re.S)
        if m and _looks_like_sender(m.group(1).strip(), name):
            sender, content = m.group(1).strip(), m.group(2).strip()
        if not content or (content.startswith("[") and any(w in content for w in _PLACEHOLDER_WORDS)):
            content = "发来一条消息"
        return {"chat": name, "sender": sender, "content": content, "source": "list"}


def debug_ocr_once() -> dict:
    """Capture the chat list once and return parsed rows (used by --ocr-check)."""
    hwnd = find_wechat_window()
    if not hwnd:
        return {"error": "微信窗口没找到"}
    img = capture_window(hwnd)
    if img is None:
        return {"error": "抓图失败（窗口可能最小化/在托盘里）"}
    watcher = ChatListWatcher(lambda _m: None, lambda _s: None)
    lines = watcher._ocr(img)
    rows = group_rows(lines)
    return {
        "size": list(img.size),
        "badges": badge_rows(img),
        "rows": rows,
    }


if __name__ == "__main__":
    def on_msg(m):
        print("MSG", m, flush=True)

    w = ChatListWatcher(on_msg, lambda s: print("STATUS", s, flush=True), 1.0)
    w.start()
    time.sleep(45)
    w.stop()
