"""Smoke test: TTS, sound playback, hotkey registration, toast parsing."""
import time

import hotkey
import notif_watcher
import sound_player
import tts_engine

print("voices:", tts_engine.list_voices())
print("hotkey parse:", hotkey.parse_hotkey("ctrl+alt+q"), hotkey.parse_hotkey("ctrl+shift+F9"))
print("access status:", notif_watcher.access_status())

# parsing checks
cases = [
    ["微信", "产品研发群", "张伟：这个版本的接口文档我下午更新一下"],
    ["微信", "李明", "晚上七点老地方见"],
    ["微信", "李明", "时间：明天下午三点"],
    ["李明", "晚上七点老地方见"],
]
for c in cases:
    print("parse", c, "->", notif_watcher.parse(c))

player = sound_player.SoundPlayer()
path = sound_player.resolve_sound("builtin:bell_soft")
print("sound path:", path)
t0 = time.time()
print("play ok:", player.play(path, 0.9), f"{time.time()-t0:.3f}s")
time.sleep(0.4)
print("is_playing:", player.is_playing())
time.sleep(2.0)
print("is_playing after:", player.is_playing())

tts = tts_engine.TTSEngine()
time.sleep(0.3)
print("tts voice:", tts.voice_name)
t0 = time.time()
tts.speak("测试，李明给你发来一条微信消息。")
time.sleep(0.6)
print("speaking:", tts.is_speaking(), f"started in {time.time()-t0:.2f}s")
time.sleep(2.6)
tts.stop()
print("stopped:", not tts.is_speaking())

hk = hotkey.HotkeyManager(lambda: print("HOTKEY FIRED"))
print("hotkey start:", hk.start("ctrl+alt+q"))
hk.stop()
print("clean exit")
