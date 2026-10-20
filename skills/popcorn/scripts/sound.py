"""Synthesized sound: soft UI effects and a background track made of plain tones, so no samples and no licenses.
mix(total, cues, voice, moods) -> stereo float32 at 48 kHz
  cues  = [(seconds, kind)]; kinds below (fx), plus 'type:<ms>' for typing ticks over that long
  voice = [(seconds, mono float32 array)]
  moods = [(seconds, mood)], mood: light | warm | tense | silent; the music ducks under the voice
Every effect is low-passed and short: bright noise bursts (hiss sweeps, cracks, buzzes) hurt at video volume."""
import os
import numpy as np

SR = 48000
rng = np.random.default_rng(7)


def t_(d): return np.arange(int(SR * d)) / SR
def env(d, a=0.005, k=8.0): t = t_(d); return np.minimum(1, t / max(a, 1e-4)) * np.exp(-k * t)
def noise(d): return rng.standard_normal(int(SR * d))
def note(n): return 440.0 * 2 ** ((n - 69) / 12)


def lp(x, cutoff):
    """one-pole low-pass; a fixed cutoff runs as a short convolution, a sweep (an array of cutoffs) sample by sample"""
    if np.ndim(cutoff) == 0:
        a = np.exp(-2 * np.pi * float(cutoff) / SR)
        k = (1 - a) * a ** np.arange(max(8, int(np.ceil(np.log(1e-4) / np.log(a)))))
        return np.convolve(x, k)[: len(x)]
    c = np.broadcast_to(np.asarray(cutoff, dtype=float), x.shape); a = np.exp(-2 * np.pi * c / SR)
    y = np.empty_like(x); s = 0.0
    for i in range(len(x)): s = (1 - a[i]) * x[i] + a[i] * s; y[i] = s
    return y


def hp(x, cutoff): return x - lp(x, cutoff)


def sine(f, d, ph=0):
    t = t_(d); f = np.broadcast_to(np.asarray(f, float), t.shape); return np.sin(2 * np.pi * np.cumsum(f) / SR + ph)


def fx(kind):
    if kind == 'click':   # a pointer click
        return 0.3 * lp(hp(noise(0.03), 2000), 6000) * env(0.03, 0.001, 160) + 0.2 * sine(2000, 0.03) * env(0.03, 0.001, 140)
    if kind == 'pop':     # something appears
        return 0.28 * sine(np.linspace(520, 860, int(SR * 0.09)), 0.09) * env(0.09, 0.002, 40)
    if kind == 'tick':    # a small change: a counter, a highlight
        return 0.14 * sine(2400, 0.04) * env(0.04, 0.001, 120)
    if kind == 'drop':    # something leaves or settles: a soft low thud
        return 0.4 * sine(np.linspace(190, 85, int(SR * 0.18)), 0.18) * env(0.18, 0.002, 22)
    if kind == 'thud':    # a heavier landing, still without noise
        return 0.5 * sine(np.linspace(110, 48, int(SR * 0.45)), 0.45) * env(0.45, 0.003, 9)
    if kind == 'knock':   # wood, a door, a box: low-passed knocks
        out = np.zeros(int(SR * 0.4))
        for s, g in ((0.0, 0.24), (0.09, 0.16)):
            b = g * lp(noise(0.06), 600) * env(0.06, 0.002, 50) + g * 0.8 * sine(np.linspace(180, 120, int(SR * 0.06)), 0.06) * env(0.06, 0.002, 50)
            i = int(SR * s); out[i:i + len(b)] += b
        return out
    if kind == 'splash':  # into water: a dull, low-passed body and a few bubbles
        d = 0.8; body = lp(noise(d), np.linspace(1100, 260, int(SR * d))) * env(d, 0.02, 5)
        bub = np.zeros(int(SR * d))
        for _ in range(5):
            s = rng.uniform(0.15, 0.6); f = rng.uniform(300, 500); b = sine(np.linspace(f, f * 1.4, int(SR * 0.05)), 0.05) * env(0.05, 0.004, 55); i = int(SR * s); bub[i:i + len(b)] += b
        return 0.24 * body + 0.04 * bub + 0.2 * sine(np.linspace(160, 70, int(SR * d)), d) * env(d, 0.004, 10)
    if kind == 'chime':   # success: two soft bell notes
        out = np.zeros(int(SR * 0.9))
        for i, f in enumerate((1318.5, 1975.5)):
            n = sum((0.6 / h) * sine(f * h, 0.8) for h in (1, 2, 3)) * env(0.8, 0.003, 5.5); s = int(SR * 0.09 * i); out[s:s + len(n)] += 0.2 * n
        return out
    if kind == 'fail':    # failure: two quiet notes going down, not a buzzer
        out = np.zeros(int(SR * 0.5))
        for i, f in enumerate((329.6, 261.6)):
            n = (sine(f, 0.26) + 0.2 * sine(2 * f, 0.26)) * env(0.26, 0.012, 9); s = int(SR * 0.16 * i); out[s:s + len(n)] += 0.12 * n
        return out
    if kind == 'glide':   # a big move (a camera pull, one thing turning into another): a soft tone that rises
        d = 0.55; t = t_(d); f = 250 * (420 / 250) ** np.clip(t / 0.4, 0, 1)
        x = sine(f, d) + 0.3 * sine(1.5 * f, d) + 0.12 * sine(2 * f, d)
        e = np.minimum(1, t / 0.07) * np.exp(-5.5 * np.maximum(0, t - 0.07)) * np.minimum(1, (d - t) / 0.08)
        return 0.11 * lp(x * e, 1800)
    if kind == 'bloom':   # a reveal or a title: a soft chord swell
        d = 0.7; t = t_(d); x = sum(g * sine(fr * (1 + 0.004 * np.sin(2 * np.pi * 5 * t)), d) for fr, g in ((392.0, 1.0), (587.3, 0.6), (784.0, 0.18)))
        e = np.minimum(1, t / 0.14) * np.exp(-4.2 * np.maximum(0, t - 0.14)) * np.minimum(1, (d - t) / 0.1)
        return 0.085 * lp(x * e, 2200)
    if kind == 'swipe':   # a scene change: a short, soft air movement, nothing bright
        d = 0.32; c = np.linspace(500, 1500, int(SR * d)); e = np.sin(np.pi * np.clip(t_(d) / d, 0, 1)) ** 2
        return 0.06 * hp(lp(noise(d), c), 250) * e
    if kind.startswith('type:'):  # typing under text that streams in
        d = int(kind.split(':')[1]) / 1000; out = np.zeros(int(SR * d) + SR // 10); t = 0.0
        while t < d:
            b = 0.1 * lp(hp(noise(0.012), 2500), 7000) * env(0.012, 0.0005, 300); i = int(SR * t); out[i:i + len(b)] += b * rng.uniform(0.5, 1.0); t += rng.uniform(0.035, 0.075)
        return out
    raise ValueError(f'unknown sound cue: {kind}')


# old or harsh names a page may still use, played as their soft counterparts; SFX_SWAP="a=b,c=d" tries others
ALIASES = {'rise': 'glide', 'swoosh': 'glide', 'whoosh': 'glide', 'hit': 'thud', 'hit2': 'thud', 'crack': 'knock'}


def add(buf, i, x, ch=None):
    """adds x into buf from sample i, clipped to the buffer; ch: one channel, or both when None"""
    if i >= len(buf) or i < 0: return
    x = x[: len(buf) - i]
    if buf.ndim == 1: buf[i:i + len(x)] += x
    elif ch is None: buf[i:i + len(x)] += x[:, None] if x.ndim == 1 else x
    else: buf[i:i + len(x), ch] += x


CHORDS = [(48, 52, 55, 59), (43, 47, 50, 55), (45, 48, 52, 57), (41, 45, 48, 53)]  # Cmaj7 G Am F


def _bed(out, t_from, t_to, mood):
    """one stretch of the track: light (pad and soft arpeggio), warm (the same, fuller, with a soft pulse), tense (a low
    drone and a ticking pulse that tightens towards its end), silent"""
    if mood == 'silent' or t_to <= t_from: return
    beat = 60 / 100; bar = 4 * beat
    if mood == 'tense':
        d = t_to - t_from; tA = t_(d)
        drone = (0.5 * np.sin(2 * np.pi * note(45) * tA) + 0.3 * np.sin(2 * np.pi * note(52) * tA)) * (0.75 + 0.25 * np.sin(2 * np.pi * 0.5 * tA))
        drone *= np.minimum(1, tA / 1.0) * np.minimum(1, (d - tA) / 0.3); add(out, int(SR * t_from), 0.09 * drone)
        s0 = 0.0
        while s0 < d:
            add(out, int(SR * (t_from + s0)), 0.05 * sine(1800, 0.03) * env(0.03, 0.0005, 120)); s0 += 0.25 if s0 < d - 3 else 0.125
        return
    t0, k = t_from, 0
    while t0 < t_to:
        ch = CHORDS[k % 4]; d = min(bar, t_to - t0) + 0.6; tt = t_(d)
        pad = sum(np.sin(2 * np.pi * note(n + 12) * tt + j) for j, n in enumerate(ch)) / 4
        pad = lp(pad, 1400) * np.minimum(1, tt / 0.25) * np.minimum(1, np.maximum(0, d - tt) / 0.5)
        add(out, int(SR * t0), (0.07 if mood == 'light' else 0.1) * pad)
        for s_ in range(8):
            st = t0 + s_ * beat / 2
            if st >= t_to: break
            p = sine(note(ch[s_ % 4] + 24), 0.45) * env(0.45, 0.002, 7); j = int(SR * st); pan = 0.35 + 0.3 * (s_ % 2); g = 0.03 if mood == 'light' else 0.045
            add(out, j, g * p * (1 - pan), 0); add(out, j, g * p * pan, 1)
        if mood == 'warm':
            for s_ in (0, 2):
                st = t0 + s_ * beat
                if st < t_to: add(out, int(SR * st), 0.14 * sine(np.linspace(110, 45, int(SR * 0.25)), 0.25) * env(0.25, 0.002, 14))
        t0 += bar; k += 1


def music(total, moods):
    out = np.zeros((int(SR * total) + SR, 2))
    moods = sorted(moods) or [(0.0, 'light')]
    for (a, m), (b, _) in zip(moods, moods[1:] + [(total, None)]): _bed(out, a, min(b, total), m)
    if moods[-1][1] != 'silent':  # a last chord that rings out under the end
        tt = t_(2.5); last = sum(np.sin(2 * np.pi * note(n + 12) * tt) for n in CHORDS[0]) / 4 * env(2.5, 0.01, 1.4)
        add(out, max(0, int(SR * (total - 2.6))), 0.08 * last)
    return out[: int(SR * total)]


def mix(total, cues, voice, moods, swap=None):
    swap = {**ALIASES, **(swap or {}), **dict(p.split('=') for p in (os.environ.get('SFX_SWAP') or '').split(',') if '=' in p)}
    n = int(SR * total)
    m = music(total, moods)
    v = np.zeros(n)
    for s, a in voice:
        i = int(SR * s); a = a[: max(0, n - i)]; v[i:i + len(a)] += a
    # the music ducks under the voice: a smoothed envelope of the voice (a running sum, fast on any length)
    e = np.abs(v); w = int(SR * 0.25); c = np.concatenate([[0.0], np.cumsum(e)]); i = np.arange(n)
    e = (c[np.clip(i + w // 2, 0, n)] - c[np.clip(i - w // 2, 0, n)]) / w; e = np.clip(e / (e.max() + 1e-9) * 6, 0, 1)
    m = m * (1 - 0.55 * e)[:, None]
    f = np.zeros(n)
    for s, kind in cues:
        if kind is None: continue
        x = fx(swap.get(kind, kind)); i = int(SR * s); x = x[: max(0, n - i)]; f[i:i + len(x)] += x
    out = m + 0.9 * np.stack([v, v], 1) + 0.6 * np.stack([f, f], 1)
    return (out / max(1.0, np.abs(out).max() / 0.95)).astype(np.float32)
