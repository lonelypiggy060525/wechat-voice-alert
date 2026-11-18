"""Generate the built-in notification sounds (soft, layered, not the WeChat beep).

Run: python gen_sounds.py
Writes 44.1 kHz stereo 16-bit WAV files into assets/sounds/.
"""
from __future__ import annotations

import math
import os
import wave

import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sounds")
os.makedirs(OUT, exist_ok=True)


def env_exp(n: int, tau: float, attack: float = 0.004) -> np.ndarray:
    t = np.arange(n) / SR
    e = np.exp(-t / tau)
    a = int(attack * SR)
    if a > 0:
        e[:a] *= np.linspace(0.0, 1.0, a)
    return e


def note(freq: float, dur: float, tau: float, amp: float = 1.0, partials=None) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    partials = partials or [(1.0, 1.0), (2.0, 0.32), (3.0, 0.12), (4.01, 0.05)]
    w = np.zeros(n)
    for mult, g in partials:
        decay = np.exp(-t / (tau / max(mult ** 0.35, 0.6)))
        w += g * np.sin(2 * math.pi * freq * mult * t) * decay
    a = int(0.004 * SR)
    if a > 0:
        w[:a] *= np.linspace(0, 1, a)
    return amp * w


def pad_to(x: np.ndarray, n: int) -> np.ndarray:
    if len(x) >= n:
        return x[:n]
    return np.concatenate([x, np.zeros(n - len(x))])


def mix(parts, total: float) -> np.ndarray:
    n = int(total * SR)
    out = np.zeros(n)
    for start, sig in parts:
        i = int(start * SR)
        seg = pad_to(sig, n - i)
        out[i:i + len(seg)] += seg
    return out


def soft_room(x: np.ndarray, delay_ms=55, gain=0.28, repeats=3) -> np.ndarray:
    """Cheap reverb: a few decaying delayed copies."""
    out = x.copy()
    d = int(delay_ms / 1000 * SR)
    for k in range(1, repeats + 1):
        g = gain * (0.55 ** (k - 1))
        shifted = np.concatenate([np.zeros(d * k), x])[: len(x)]
        out += g * shifted
    return out


def stereo(x: np.ndarray, width: float = 0.08) -> np.ndarray:
    """Tiny haas widening so it feels placed, not mono-harsh."""
    d = int(width * 0.01 * SR) + 1
    left = np.concatenate([x, np.zeros(d)])[: len(x)]
    right = np.concatenate([np.zeros(d), x])[: len(x)]
    return np.stack([left, right], axis=1)


def save(name: str, signal: np.ndarray, peak: float = 0.62) -> None:
    m = np.max(np.abs(signal)) or 1.0
    signal = signal / m * peak
    # 3 ms fade out to avoid clicks
    f = int(0.003 * SR)
    signal[-f:] *= np.linspace(1, 0, f)[:, None] if signal.ndim == 2 else np.linspace(1, 0, f)
    pcm = np.clip(signal, -1, 1)
    pcm = (pcm * 32767).astype("<i2")
    path = os.path.join(OUT, name)
    with wave.open(path, "wb") as w:
        w.setnchannels(2 if pcm.ndim == 2 else 1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    print("wrote", path, f"{len(signal)/SR:.2f}s")


def bell_soft():
    """Glass bell, C6 with a soft octave shimmer."""
    base = note(1046.5, 2.0, 0.55, 0.9, [(1, 1.0), (2.0, 0.25), (3.0, 0.08), (5.4, 0.03)])
    shimmer = note(2093.0, 1.2, 0.28, 0.18)
    sig = mix([(0.0, base), (0.02, shimmer)], 2.2)
    return stereo(soft_room(sig, 60, 0.22, 3))


def marimba():
    """Warm two-note marimba: G5 -> D6."""
    a = note(784.0, 1.1, 0.30, 1.0, [(1, 1.0), (3.98, 0.20), (9.0, 0.04)])
    b = note(1174.7, 1.4, 0.42, 0.85, [(1, 1.0), (3.98, 0.22), (9.0, 0.05)])
    sig = mix([(0.0, a), (0.16, b)], 1.9)
    return stereo(soft_room(sig, 45, 0.18, 2))


def water_drop():
    """Falling pitch drop with a rounded tail."""
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    f = 1500 * np.exp(-t / 0.12) + 620
    phase = 2 * math.pi * np.cumsum(f) / SR
    body = np.sin(phase) * np.exp(-t / 0.16)
    click = np.sin(2 * math.pi * 2600 * t) * np.exp(-t / 0.02) * 0.25
    sig = mix([(0.0, body + click), (0.045, 0.25 * body)], 1.0)
    return stereo(soft_room(sig, 70, 0.30, 3))


def chime_triad():
    """C5-E5-G5 arpeggio, gentle and bright."""
    a = note(523.25, 1.6, 0.6, 0.8)
    b = note(659.25, 1.5, 0.6, 0.75)
    c = note(783.99, 1.9, 0.75, 0.7)
    sig = mix([(0.0, a), (0.11, b), (0.22, c)], 2.4)
    return stereo(soft_room(sig, 75, 0.26, 3))


def soft_ping():
    """Minimal, very short - good for high message volume."""
    a = note(1318.5, 0.5, 0.14, 1.0, [(1, 1.0), (2.0, 0.18)])
    sig = mix([(0.0, a)], 0.7)
    return stereo(soft_room(sig, 35, 0.15, 2))


def wooden_tap():
    """Dry wooden knock - unobtrusive."""
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    body = np.sin(2 * math.pi * 320 * t) * np.exp(-t / 0.045)
    body += 0.4 * np.sin(2 * math.pi * 720 * t) * np.exp(-t / 0.025)
    noise = np.random.default_rng(3).normal(0, 1, n) * np.exp(-t / 0.006) * 0.25
    sig = mix([(0.0, body + noise)], 0.45)
    return stereo(soft_room(sig, 25, 0.12, 2))


if __name__ == "__main__":
    save("bell_soft.wav", bell_soft())
    save("marimba.wav", marimba())
    save("water_drop.wav", water_drop(), 0.55)
    save("chime_triad.wav", chime_triad())
    save("soft_ping.wav", soft_ping(), 0.5)
    save("wooden_tap.wav", wooden_tap(), 0.55)
