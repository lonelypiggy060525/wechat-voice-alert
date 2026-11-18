"""Read WeChat toasts from the Windows notification center (no injection, no DB access)."""
from __future__ import annotations

import asyncio
import re
import threading
import time
from typing import Callable, Optional

from winsdk.windows.ui.notifications import NotificationKinds
from winsdk.windows.ui.notifications.management import (
    UserNotificationListener,
    UserNotificationListenerAccessStatus,
)

WECHAT_HINTS = ("微信", "wechat", "weixin", "tencent")

# 微信 4.x toast text layout: [应用名, 会话名, 发送者: 正文]
# older/other builds: [会话名, 正文]
_SPLIT_RE = re.compile(r"^(.{1,20}?)[：:]\s*(\S.*)$", re.S)

# prefixes that look like a colon in normal prose rather than a sender nickname
_NOT_A_NAME = {
    "时间", "地点", "地址", "内容", "标题", "主题", "备注", "注意", "提醒", "电话",
    "价格", "链接", "网址", "会议", "日期", "要求", "答案", "问题", "原因", "结果",
    "温馨提示", "注意啦", "更新", "通知", "公告", "总结", "计划", "安排",
}


def _looks_like_sender(prefix: str, chat: str) -> bool:
    if not prefix or prefix == chat:
        return False
    if prefix in _NOT_A_NAME:
        return False
    if len(prefix) > 8:
        return False
    if any(ch.isspace() for ch in prefix):
        return False
    # a nickname: letters/digits/CJK/middot, no punctuation soup
    return bool(re.fullmatch(r"[0-9A-Za-z\u4e00-\u9fa5·_\-\.]{1,8}", prefix))


def toast_texts(notification) -> list[str]:
    try:
        binding = notification.notification.visual.get_binding("ToastGeneric")
        if binding:
            return [e.text for e in binding.get_text_elements() if e.text]
    except Exception:
        pass
    try:
        binding = notification.notification.visual.get_binding("ToastText02")
        if binding:
            return [e.text for e in binding.get_text_elements() if e.text]
    except Exception:
        pass
    return []


def is_wechat(display_name: str, aumid: str) -> bool:
    hay = f"{display_name or ''} {aumid or ''}".lower()
    return any(h in hay for h in WECHAT_HINTS)


def parse(texts: list[str]) -> tuple[str, str, str]:
    """Return (chat, sender, content)."""
    texts = [t.strip() for t in texts if t and t.strip()]
    if not texts:
        return "", "", ""
    if len(texts) >= 3:
        chat, body = texts[1], " ".join(texts[2:])
    elif len(texts) == 2:
        chat, body = texts[0], texts[1]
    else:
        chat, body = texts[0], texts[0]

    sender, content = chat, body
    m = _SPLIT_RE.match(body)
    if m:
        left, right = m.group(1).strip(), m.group(2).strip()
        if _looks_like_sender(left, chat):
            sender, content = left, right
    return chat, sender, content


def access_status() -> int:
    try:
        return int(UserNotificationListener.current.get_access_status())
    except Exception:
        return -1


def request_access() -> int:
    async def _go():
        listener = UserNotificationListener.current
        status = listener.get_access_status()
        if status != UserNotificationListenerAccessStatus.ALLOWED:
            status = await listener.request_access_async()
        return int(status)

    try:
        return asyncio.run(_go())
    except Exception:
        return -1


class NotificationWatcher(threading.Thread):
    """Polls the notification center and calls on_message(dict) for new WeChat toasts."""

    def __init__(self, on_message: Callable[[dict], None], on_status: Callable[[str], None],
                 interval_ms: int = 600) -> None:
        super().__init__(name="notif-watcher", daemon=True)
        self.on_message = on_message
        self.on_status = on_status
        self.interval = max(0.2, interval_ms / 1000)
        self._stop = threading.Event()
        self._seen: dict[tuple, float] = {}
        self._last_content = ("", 0.0)

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        try:
            asyncio.run(self._loop())
        except Exception as exc:  # pragma: no cover - defensive
            self.on_status(f"监听异常：{exc}")

    async def _loop(self) -> None:
        try:
            listener = UserNotificationListener.current
        except Exception as exc:
            self.on_status(f"无法访问通知中心：{exc}")
            return
        status = listener.get_access_status()
        if status != UserNotificationListenerAccessStatus.ALLOWED:
            self.on_status("等待通知权限…")
            status = await listener.request_access_async()
        if status != UserNotificationListenerAccessStatus.ALLOWED:
            self.on_status("没有通知访问权限，请在 Windows 设置里允许")
            return
        self.on_status("运行中")

        start = time.time() - 2
        while not self._stop.is_set():
            try:
                notifs = await listener.get_notifications_async(NotificationKinds.TOAST)
            except Exception as exc:
                self.on_status(f"读取通知失败：{exc}")
                await asyncio.sleep(3)
                continue

            now = time.time()
            for n in notifs:
                try:
                    display = n.app_info.display_info.display_name or ""
                    aumid = n.app_info.app_user_model_id or ""
                    if not is_wechat(display, aumid):
                        continue
                    try:
                        created = n.creation_time.timestamp()
                    except Exception:
                        created = now
                    if created < start:
                        continue
                    texts = toast_texts(n)
                    if not texts:
                        continue
                    sig = (int(n.id), tuple(texts))
                    if sig in self._seen:
                        continue
                    self._seen[sig] = now
                    chat, sender, content = parse(texts)
                    if not content:
                        continue
                    key = (sender, content)
                    if key == self._last_content[0] and now - self._last_content[1] < 3:
                        continue
                    self._last_content = (key, now)
                    self.on_message({
                        "chat": chat,
                        "sender": sender,
                        "content": content,
                        "texts": texts,
                        "app": display,
                        "time": created,
                    })
                except Exception:
                    continue

            # prune old signatures
            if len(self._seen) > 400:
                cutoff = now - 3600
                self._seen = {k: v for k, v in self._seen.items() if v > cutoff}

            await asyncio.sleep(self.interval)


def wechat_running() -> bool:
    import subprocess
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True).stdout.decode("gbk", "replace")
    except Exception:
        return False
    return "weixin.exe" in out.lower() or "wechat.exe" in out.lower()


def wechat_focused() -> bool:
    """True when the WeChat main window is the foreground window."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32")
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        cls = ctypes.create_unicode_buffer(128)
        user32.GetClassNameW(hwnd, cls, 128)
        if not cls.value.startswith("Qt51514QWindowIcon"):
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        import subprocess
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH", "/FI", f"PID eq {pid.value}"],
                             capture_output=True).stdout.decode("gbk", "replace")
        return "weixin.exe" in out.lower() or "wechat.exe" in out.lower()
    except Exception:
        return False


if __name__ == "__main__":
    print("access status:", access_status())
    print("wechat running:", wechat_running())

    def _on_msg(m):
        print("MESSAGE", m)

    w = NotificationWatcher(_on_msg, print, 600)
    w.start()
    time.sleep(60)
    w.stop()
