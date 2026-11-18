"""Check the Edge neural voice path: latency, playback, interrupt."""
import time

import tts_engine

print("options:", [v for v, _ in tts_engine.voice_options()][:8])
e = tts_engine.TTSEngine("edge:zh-CN-XiaoxiaoNeural", 0, 100)
time.sleep(0.5)

t0 = time.time()
e.speak("张三说：晚上七点老地方见。")
time.sleep(1.0)
print(f"speaking after 1.0s: {e.is_speaking()}")
time.sleep(2.5)
print(f"finished: {not e.is_speaking()}  total {time.time()-t0:.1f}s")

print("-- interrupt test --")
e.speak("这是一段比较长的话，用来测试打断是不是立刻生效，后面还有很多很多内容要继续念下去。")
time.sleep(1.2)
print("before stop:", e.is_speaking())
e.stop()
time.sleep(0.6)
print("after stop:", e.is_speaking())   # expect False

print("-- sapi fallback test --")
e2 = tts_engine.TTSEngine("sapi:Microsoft Huihui Desktop - Chinese (Simplified)", 0, 100)
e2.speak("离线发音测试。")
time.sleep(2.5)
print("sapi done:", not e2.is_speaking())
