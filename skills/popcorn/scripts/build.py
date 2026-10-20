"""Builds a video from a project's plan.json: renders the scenes frame by frame in parallel headless browsers (only the
scenes whose page, kit or settings changed since their last render), joins them, lays the voice, the scenes' sound cues
and the music under them, encodes, and writes what to check: a sheet of frames around every transition and a timeline.
Usage: build.py <plan.json> [--draft | --final | --profile <name>] [--browsers N] [--frames-only] [--force]
  --draft  480p, fewer frames a second, JPEG frames, the fastest encoder there is (a GPU one when present)
  --final  1080p, full frame rate, PNG frames, the quality encoder (the default)
  --profile gif-draft | gif   an animated GIF instead of a video: its cheap preview, then the real one
A plan with "over": {"file": <video>} lays the voice on an existing video instead: no scenes are rendered, the final keeps
the video's own picture as it is.
--variant <name>   one of the plan's "variants" (a version with or without a part, etc.)
A plan's "cover" goes in as frame 0 and as the file's embedded cover; "captions" writes a .srt and, with "burn", draws
them in a strip of their own under the scene.
Sizes name the picture's short side. Writes <project>/out/<name>-<profile>-<size>p.mp4 (or .gif), ...-transitions.png
and ...-timeline.json; an earlier build's files move to out/old/<time>/ instead of being overwritten."""
import glob, json, os, re, shutil, subprocess, sys, time, wave
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from urllib.parse import quote
import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageOps
import common as C
import sound
from gif import make_gif

ARGS = sys.argv[1:]


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


def scene_query(s):
    if not s.get('tag'): return ''
    return f"tag={quote(s['tag'])}&tone={s.get('tone', 'bad')}" + (f"&tagin={s['tagin']}" if 'tagin' in s else '')


def scene_url(base, s): return C.page_url(base, s['page'], scene_query(s))


def cover_picture(plan, cover, size, path):
    """the plan's cover at the frame's size: its image, or its page at its moment; cropped to the frame's shape, never
    stretched. Returns a warning when the shapes differ"""
    W, H = size
    if cover.get('image'): im = Image.open(os.path.join(plan['_root'], cover['image'])).convert('RGB')
    else:
        raw = path + '-raw.png'; sw, sh = plan['stage']
        C.stills(plan, [dict(page=cover['page'], t=cover.get('t', 0), out=raw, width=sw, height=sh, scale=max(W / sw, H / sh))], 1)
        im = Image.open(raw).convert('RGB')
    ImageOps.fit(im, (W, H), Image.LANCZOS).save(path)
    if abs(im.width / im.height - W / H) > 0.02:
        return f"the cover ({im.width}x{im.height}) is not the frame's shape ({W}x{H}): its edges were cropped; give it the frame's shape to choose what stays"


def embed_cover(ff, final, jpg):
    """the cover inside the file, as the picture players and feeds show for it"""
    tmp = final[:-4] + '.with-cover.mp4'
    C.run(ff, '-y', '-loglevel', 'error', '-i', final, '-i', jpg, '-map', '0', '-map', '1', '-c', 'copy', '-disposition:v:1', 'attached_pic', '-movflags', '+faststart', tmp)
    os.replace(tmp, final)


def jobs_for(plan, prof, force):
    jobs = []
    for s in plan['scenes']:
        key = C.content_key(plan, s['page'], s.get('tag'), s.get('tone'), s['from'], s['to'], s.get('speed', 1), prof['fps'], prof['scale'], prof['format'], plan['scheme'], plan['stage'])
        d = os.path.join(plan['_root'], '.render', prof['name'], s.get('_cache', s['id'])); mp = os.path.join(d, 'meta.json')
        cached = not force and os.path.exists(mp) and json.load(open(mp)).get('key') == key
        jobs.append(dict(scene=s, dir=d, key=key, cached=cached))
    blank = dict(id='_blank', page='kit/blank.html', **{'from': 0, 'to': 1000 / prof['fps'], 'speed': 1})
    d = os.path.join(plan['_root'], '.render', prof['name'], '_blank')
    key = C.content_key(plan, blank['page'], prof['scale'], prof['format'], plan['scheme'], plan['stage'])
    jobs.append(dict(scene=blank, dir=d, key=key, cached=not force and os.path.exists(os.path.join(d, 'meta.json')) and json.load(open(os.path.join(d, 'meta.json'))).get('key') == key))
    return jobs


def render(plan, prof, todo, n_browsers):
    with C.server(plan) as base, C.browsers(plan, n_browsers) as ports:
        free = Queue()
        for p in ports: free.put(p)

        def one(job):
            s = job['scene']; port = free.get()
            try:
                env = dict(os.environ, CDP_PORT=str(port), FMT=prof['format'], SEG_KEY=job['key'])
                C.run('node', os.path.join(C.HERE, 'render.mjs'), scene_url(base, s), job['dir'], s['from'], s['to'], s.get('speed', 1),
                      prof['fps'], prof['scale'], plan['stage'][0], plan['stage'][1], plan['scheme'], env=env)
            finally: free.put(port)
        # the longest scenes first, so the browsers finish together
        list(ThreadPoolExecutor(len(ports)).map(one, sorted(todo, key=lambda j: -C.scene_secs(j['scene']))))


def compose(a_files, b_files, out_dir, blank, kind, ext):
    """the last frames of one scene and the first of the next, made into the transition between them"""
    os.makedirs(out_dir, exist_ok=True); K = len(a_files); W = blank.width; d = round(0.07 * W); outs = []
    for k in range(K):
        u = (k + 1) / (K + 1); e = u * u * (3 - 2 * u)
        A = Image.open(a_files[k]).convert('RGB'); B = Image.open(b_files[k]).convert('RGB')
        if kind == 'fade': f = Image.blend(A, B, e)
        else:  # swipe: the old scene slides a little to the left and fades, the new one comes in from the right
            a2 = blank.copy(); a2.paste(A, (-round(d * e), 0)); b2 = blank.copy(); b2.paste(B, (round(d * (1 - e)), 0))
            f = Image.blend(Image.blend(blank, a2, 1 - e), b2, min(1.0, u * 2.2))
        p = os.path.join(out_dir, f'{k:05d}.{ext}'); f.save(p, quality=92) if ext == 'jpg' else f.save(p); outs.append(p)
    return outs


def read_wav(path):
    with wave.open(path) as w:
        if w.getframerate() != sound.SR or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise SystemExit(f'{path}: want 48 kHz mono 16-bit (voice_prep.py makes it)')
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def write_wav(path, x):
    with wave.open(path, 'w') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(sound.SR); w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def music_track(plan, total, ff):
    m = plan.get('music')
    if not isinstance(m, dict) or not m.get('file'): return None
    raw = os.path.join(plan['_root'], '.render', 'music.raw')
    C.run(ff, '-y', '-loglevel', 'error', '-stream_loop', '-1', '-i', os.path.join(plan['_root'], m['file']), '-t', f'{total + 1:.2f}',
          '-ac', '2', '-ar', str(sound.SR), '-f', 'f32le', raw)
    x = np.fromfile(raw, dtype=np.float32).reshape(-1, 2)[: int(sound.SR * total)] * float(m.get('gain', 0.35))
    fade = min(len(x), int(sound.SR * 2.0)); x[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return x


def sheet(seq, bounds, fps, path, labels):
    """frames around every transition, one row each: a frame from the scene before, the transition, the scene after"""
    offs = [-0.5, -0.2, 0.0, 0.2, 0.5]; tw = 300
    rows = []
    for (b, lab) in zip(bounds, labels):
        row = []
        for o in offs:
            i = min(len(seq) - 1, max(0, b + round(o * fps)))
            im = Image.open(seq[i]).convert('RGB'); row.append((im.resize((tw, round(im.height * tw / im.width))), i / fps))
        rows.append((row, lab))
    if not rows: return
    th = rows[0][0][0][0].height; W = 20 + len(offs) * (tw + 10); H = 20 + len(rows) * (th + 48)
    img = Image.new('RGB', (W, H), (245, 246, 248)); d = ImageDraw.Draw(img); f, fb = C.font(15), C.font(16, True)
    y = 14
    for row, lab in rows:
        d.text((20, y), lab, font=fb, fill=(18, 21, 26)); y += 24
        for k, (im, t) in enumerate(row):
            x = 20 + k * (tw + 10); img.paste(im, (x, y)); d.rectangle([x - 1, y - 1, x + tw, y + th], outline=(214, 218, 224))
            lab_t = f'{int(t // 60)}:{t % 60:05.2f}'; lw = d.textlength(lab_t, font=f)
            d.rounded_rectangle([x + 6, y + th - 28, x + 18 + lw, y + th - 6], 6, fill=(18, 21, 26)); d.text((x + 12, y + th - 27), lab_t, font=f, fill=(255, 255, 255))
        y += th + 24
    img.save(path)


def keep_previous(stem):
    """an earlier build's results move to out/old/<time>/, so versions stay to compare and to merge"""
    old = [f for f in glob.glob(glob.escape(stem) + '*') if os.path.isfile(f)]
    if not old: return None
    d = os.path.join(os.path.dirname(stem), 'old', time.strftime('%Y%m%d-%H%M%S')); os.makedirs(d, exist_ok=True)
    for f in old: shutil.move(f, os.path.join(d, os.path.basename(f)))
    return d


def loudness(ff, path):
    r = subprocess.run([ff, '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128=framelog=quiet', '-f', 'null', '-'], capture_output=True, text=True, errors='replace')
    for line in reversed(r.stderr.splitlines()):
        if line.strip().startswith('I:'): return float(line.split()[1])
    return None


def duck(track, voice, n, depth=0.6):
    """a track stepping back under the voice: a smoothed envelope of the voice (a running sum, fast on any length)"""
    v = np.zeros(n)
    for s, a in voice: i = int(sound.SR * s); a = a[: max(0, n - i)]; v[i:i + len(a)] += np.abs(a)
    w = int(sound.SR * 0.25); c = np.concatenate([[0.0], np.cumsum(v)]); ii = np.arange(n)
    e = (c[np.clip(ii + w // 2, 0, n)] - c[np.clip(ii - w // 2, 0, n)]) / w; e = np.clip(e / (e.max() + 1e-9) * 6, 0, 1)
    return track[:n] * (1 - depth * e)[: len(track), None]


def voiceover(plan, name, prof):
    """a voice-over laid on an existing video: its picture stays as it is (copied in the final, a small copy in the
    draft), its own sound steps back under the voice. plan "over": {"file": <video>, "gain": 1}; voice "at" = seconds
    from the video's start"""
    root, ff = plan['_root'], C.ffmpeg(); over = plan['over']; src = os.path.join(root, over['file'])
    info = subprocess.run([ff, '-hide_banner', '-i', src], capture_output=True, text=True, errors='replace').stderr
    hh, mm, ss = re.search(r'Duration: (\d+):(\d+):([\d.]+)', info).groups(); total = int(hh) * 3600 + int(mm) * 60 + float(ss)
    vo = plan.get('voice') or {}; vdir = os.path.join(root, vo.get('dir', 'voice')); voice, warn, tl, caps = [], [], [], []
    for ln in vo.get('lines', []):
        p = os.path.join(vdir, f"{ln.get('file', ln['id'])}.wav")
        if not os.path.exists(p): warn.append(f"no voice file for line {ln['id']} (silent there)"); continue
        a = read_wav(p); s0 = float(ln.get('at', 0)); voice.append((s0, a, ln['id'])); tl.append(dict(id=ln['id'], start=round(s0, 2), end=round(s0 + len(a) / sound.SR, 2)))
        caps += caption_chunks(ln.get('caption') or ln.get('text', ''), s0, len(a) / sound.SR, int((plan.get('captions') or {}).get('words', 7)))
    voice.sort(key=lambda x: x[0])
    for (s1, a1, l1), (s2, _, l2) in zip(voice, voice[1:]):
        e1 = s1 + len(a1) / sound.SR
        if e1 > s2 - 0.15: warn.append(f'voice lines {l1} and {l2} ' + (f'overlap by {e1 - s2:.2f}s' if e1 > s2 else f'have only {s2 - e1:.2f}s between them'))
    for s0, a, l in voice:
        if s0 + len(a) / sound.SR > total: warn.append(f'line {l} runs {s0 + len(a) / sound.SR - total:.2f}s past the end of the video')
    n = int(sound.SR * total); raw = os.path.join(root, '.render', 'over-sound.raw'); os.makedirs(os.path.dirname(raw), exist_ok=True)
    have_sound = 'Audio:' in info
    if have_sound:
        C.run(ff, '-y', '-loglevel', 'error', '-i', src, '-vn', '-ac', '2', '-ar', str(sound.SR), '-f', 'f32le', raw)
        own = np.fromfile(raw, dtype=np.float32).reshape(-1, 2)[:n] * float(over.get('gain', 1.0))
        own = np.pad(own, ((0, max(0, n - len(own))), (0, 0)))
    else: own = np.zeros((n, 2))
    audio = sound.mix(total, [], [(s, a) for s, a, _ in voice], [(0.0, 'silent')]) + duck(own, [(s, a) for s, a, _ in voice], n)
    track = music_track(plan, total, ff)
    if track is not None: audio = audio + duck(track, [(s, a) for s, a, _ in voice], n)
    aw = os.path.join(root, '.render', f'{name}-audio.wav'); write_wav(aw, audio / max(1.0, np.abs(audio).max() / 0.95))
    os.makedirs(os.path.join(root, 'out'), exist_ok=True)
    stem = os.path.join(root, 'out', f"{plan['name']}-{name}-{str(prof['short']) + 'p' if name != 'final' else 'original'}"); moved = keep_previous(stem)
    m = re.search(r'Video:.*?(\d{2,5})x(\d{2,5})', info); w, h = (int(m[1]), int(m[2])) if m else (16, 9)
    if name == 'final': pic = ['-c:v', 'copy']; size = (w, h)  # the picture as it is: no re-render, no re-encode
    else:  # a small copy, sized by its short side, wide or tall
        pic = ['-vf', f"scale=-2:{prof['short']}" if w >= h else f"scale={prof['short']}:-2", '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28']
        k = prof['short'] / min(w, h); size = (2 * round(w * k / 2), 2 * round(h * k / 2))
    target = plan.get('loudness', -16); final = stem + '.mp4'
    C.run(ff, '-y', '-loglevel', 'error', '-i', src, '-i', aw, '-map', '0:v:0', '-map', '1:a:0', *pic, '-af', f'loudnorm=I={target}:TP=-1.5:LRA=11',
          '-ar', '48000', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', final)
    caps.sort()
    if caps: write_srt(caps, stem + '.srt')
    if (plan.get('captions') or {}).get('burn'):
        warn.append("subtitles aren't burned into a voice-over (its picture stays as it is): upload the .srt with the video, or use scenes with video(...)")
    if plan.get('cover'):  # embedded and given as a picture; frame 0 stays the video's own
        w_ = cover_picture(plan, plan['cover'], size, stem + '-cover.jpg'); embed_cover(ff, final, stem + '-cover.jpg')
        if w_: warn.append(w_)
    json.dump(dict(total=round(total, 2), voice=tl), open(stem + '-timeline.json', 'w'), indent=1)
    print(f'\n{final}\n  voice-over on {over["file"]}: {total:.1f} s, {os.path.getsize(final) / 1e6:.2f} MB, loudness {loudness(ff, final)} LUFS (target {target})'
          + (f'\n  the earlier build is in {moved}' if moved else ''))
    made = [stem + x for x in ('-timeline.json', '.srt', '-cover.jpg') if os.path.exists(stem + x)]
    print('  also: ' + ', '.join(os.path.basename(x) for x in made))
    for w_ in warn: print('  ! ' + w_)


def caption_chunks(text, start, dur, words=7):
    """a voice line's text in short pieces, one on screen at a time, each timed by its share of the line's words"""
    ws = text.split()
    if not ws: return []
    chunks, cur = [], []
    for w in ws:
        cur.append(w)
        if len(cur) >= words or (w[-1] in '.,;:!?' and len(cur) >= max(2, words // 2)): chunks.append(cur); cur = []
    if cur: chunks.append(cur)
    if len(chunks) > 1 and len(chunks[-1]) == 1: last = chunks.pop(); chunks[-1] += last  # a lone last word would only flash
    out, t = [], start
    for c in chunks:
        d = dur * len(c) / len(ws); out.append((t, t + d, ' '.join(c))); t += d
    return out


def write_srt(caps, path):
    def ts(x):
        ms = int(round(x * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
        return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'
    with open(path, 'w', encoding='utf-8') as f:
        for i, (a, b, t) in enumerate(caps, 1): f.write(f'{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n')


def wrap_text(d, text, font, width):
    out, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if cur and d.textlength(t, font=font) > width: out.append(cur); cur = w
        else: cur = t
    return out + ([cur] if cur else [])


def burn_captions(seq, caps, fps, out_dir, strip, bg, ext, keep_first, place='bottom'):
    """subtitles in a strip of their own under the scene (or over it: place 'top'), so they never cover it; one at a
    time, wrapped and sized to the frame's width. The scene shrinks to make room, with margins at its sides"""
    os.makedirs(out_dir, exist_ok=True)
    W, H = Image.open(seq[0]).size; sh = round(H * strip); ah = H - sh; top = place == 'top'
    bgc = ImageColor.getrgb(bg); d0 = ImageDraw.Draw(Image.new('RGB', (8, 8)))

    def fit(text):  # the largest size at which the text fits the width in the lines the strip holds
        for size in range(max(14, round(min(sh * 0.34, W * 0.05))), 11, -2):
            f = C.font(size, True); lines = wrap_text(d0, text, f, W * 0.86)
            if len(lines) * size * 1.25 + size * 0.5 <= sh * 0.92 and all(d0.textlength(l, font=f) <= W * 0.86 for l in lines): break
        return f, lines
    layout = {c: fit(c) for _, _, c in caps}

    def one(i):
        if keep_first and i == 0: return seq[0]
        t = i / fps; text = next((c for a, b, c in caps if a <= t < b), '')
        im = Image.open(seq[i]).convert('RGB'); s = min(W / im.width, ah / im.height)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
        cv = Image.new('RGB', (W, H), bgc); cv.paste(im, ((W - im.width) // 2, sh if top else 0))
        if text:
            d = ImageDraw.Draw(cv); font, lines = layout[text]
            lh = font.size * 1.25; bw = max(d.textlength(l, font=font) for l in lines) + font.size * 1.2; bh = lh * len(lines) + font.size * 0.5
            x0, y0 = (W - bw) / 2, (0 if top else ah) + (sh - bh) / 2
            d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], round(font.size * 0.35), fill=(18, 21, 26))
            for k, l in enumerate(lines): d.text(((W - d.textlength(l, font=font)) / 2, y0 + font.size * 0.25 + k * lh), l, font=font, fill=(255, 255, 255))
        p = os.path.join(out_dir, f'{i:05d}.{ext}'); cv.save(p, quality=92) if ext == 'jpg' else cv.save(p)
        return p
    return list(ThreadPoolExecutor(os.cpu_count() or 4).map(one, range(len(seq))))


def nearly_empty(path):
    lo, hi = Image.open(path).convert('L').getextrema()
    return hi - lo < 60


def main():
    plan = C.variant(C.load_plan(ARGS[0]), arg('--variant')); root = plan['_root']; C.lock(plan)
    name = arg('--profile') or ('draft' if '--draft' in ARGS else 'final')
    prof = C.profile(plan, name); ext = 'jpg' if prof['format'] == 'jpeg' else 'png'
    if plan.get('over'): return voiceover(plan, name, prof)
    frames_only = '--frames-only' in ARGS; is_gif = name.startswith('gif')
    t_start = time.time()
    jobs = jobs_for(plan, prof, '--force' in ARGS); todo = [j for j in jobs if not j['cached']]
    nb = int(arg('--browsers', C.default_browsers(len(todo))))
    print(f'{len(todo)} of {len(jobs)} scenes to render ({name}, {prof["fps"]} fps, {prof["width"]}x{prof["height"]}), {min(nb, max(1, len(todo)))} browsers', flush=True)
    px = prof['width'] * prof['height'] * (0.04 if prof['format'] == 'jpeg' else 0.15)  # bytes a frame, roughly
    est = sum(C.scene_secs(j['scene']) * prof['fps'] for j in todo) * px
    if (plan.get('captions') or {}).get('burn') and not is_gif and not frames_only:  # the subtitled copy of every frame
        est += sum(C.scene_secs(s) for s in plan['scenes']) * prof['fps'] * px
    if est: C.disk_check(root, est, 'the frames')
    if todo:
        render(plan, prof, todo, min(nb, len(todo)))
    t_render = time.time()
    if todo:  # a capture that crawls is usually another job holding the GPU or the CPU, not the scenes
        n = sum(json.load(open(os.path.join(j['dir'], 'meta.json')))['frames'] for j in todo)
        per = (t_render - t_start) * min(nb, len(todo)) / max(1, n)
        if per > 1.0:
            print(f'  ! capture is slow: {per:.1f} s a frame in each browser. Another job may be holding the GPU or the CPU '
                  '(a voice model, another render, etc.): look before changing the scenes or the scripts', flush=True)
    scenes = plan['scenes']; dirs = {j['scene']['id']: j['dir'] for j in jobs}
    if frames_only:
        for s in scenes: print(dirs[s['id']])
        print(f'frames in {t_render - t_start:.0f} s'); return
    fps = prof['fps']; ff = C.ffmpeg(); warn = []
    meta = [json.load(open(os.path.join(dirs[s['id']], 'meta.json'))) for s in scenes]
    files = [[os.path.join(dirs[s['id']], f'{k:05d}.{m["ext"]}') for k in range(m['frames'])] for s, m in zip(scenes, meta)]
    bm = json.load(open(os.path.join(dirs['_blank'], 'meta.json')))
    blank = Image.open(os.path.join(dirs['_blank'], f'00000.{bm["ext"]}')).convert('RGB')
    tr = plan.get('transition') or {}; secs = float(tr.get('secs', 0.3))
    # the picture: each scene, and between two scenes their overlapping frames made into the transition
    seq, starts, bounds, kinds = [], [0.0], [], []
    for i, s in enumerate(scenes):
        kind = (s.get('transition') or tr.get('kind', 'swipe')) if i < len(scenes) - 1 else 'cut'
        kind = 'cut' if kind in ('none', 'cut') else kind
        K = min(max(1, round(secs * fps)), len(files[i]), len(files[i + 1])) if kind != 'cut' else 0
        head = kinds[-1][1] if kinds else 0
        seq += files[i][head: len(files[i]) - K]
        if i < len(scenes) - 1:
            bounds.append(len(seq) + K // 2)
            if K: seq += compose(files[i][-K:], files[i + 1][:K], os.path.join(root, '.render', name, f'_x{i + 1}'), blank, kind, ext)
            starts.append(len(seq) / fps - K / fps); kinds.append((kind, K))
    total = len(seq) / fps
    # frame 0 is what a feed or a player shows before play: the plan's cover goes there (and into the file as its cover)
    cover = plan.get('cover'); cimg = None
    if cover and is_gif: warn.append("a GIF has no cover: its first frame is part of the loop, so the plan's cover is left out")
    elif cover:  # it replaces frame 0 only: on play it shows for one frame, then the first scene runs
        cimg = os.path.join(root, '.render', name, f'_cover.{ext}'); os.makedirs(os.path.dirname(cimg), exist_ok=True)
        w_ = cover_picture(plan, cover, Image.open(seq[0]).size, cimg)
        if w_: warn.append(w_)
        seq[0] = cimg
    elif not is_gif and nearly_empty(seq[0]):
        warn.append('frame 0 is nearly empty: a feed or a player shows it before play. Give the plan a "cover" (the hook picture)')
    os.makedirs(os.path.join(root, 'out'), exist_ok=True)
    stem = os.path.join(root, 'out', f"{plan['name']}-{name}-{prof['short']}p"); moved = keep_previous(stem)
    labels = [f'{scenes[i]["id"]} -> {scenes[i + 1]["id"]}  ({kinds[i][0]})' for i in range(len(kinds))]
    cap = prof.get('max_mb', plan.get('max_mb'))
    if is_gif:  # no sound; the loop's seam (its last frame back to its first) is checked like a transition
        mb = make_gif(seq, fps, stem + '.gif', prof['width'], int(prof.get('colors', 192)))
        sheet(seq + seq[:round(0.6 * fps)], bounds + [len(seq)], fps, stem + '-transitions.png', labels + ['the loop: last frame -> first frame'])
        print(f'\n{stem}.gif\n  {total:.1f} s, {prof["width"]}x{prof["height"]}, {fps} fps, {mb:.2f} MB')
        print(f'  check: {stem}-transitions.png (frames around every transition and the loop seam)' + (f'; the earlier build is in {moved}' if moved else ''))
        json.dump(dict(total=round(total, 2), scenes=[dict(id=s['id'], start=round(starts[i], 2), secs=round(meta[i]['secs'], 2)) for i, s in enumerate(scenes)]),
                  open(stem + '-timeline.json', 'w'), indent=1)
        for i, s in enumerate(scenes): print(f'  {int(starts[i] // 60)}:{starts[i] % 60:04.1f}  +{meta[i]["secs"]:.1f}s  {s["id"]}')
        if cap and mb > cap: print(f'  ! {mb:.1f} MB is over the cap of {cap} MB: fewer colours, a smaller width or a shorter loop')
        for w_ in warn: print('  ! ' + w_)
        return
    # the voice: each line where the plan puts it, checked for overlaps and for running past its scene
    idx = {s['id']: i for i, s in enumerate(scenes)}
    vo = plan.get('voice') or {}; vdir = os.path.join(root, vo.get('dir', 'voice')); voice, missing, timeline_vo, caps = [], [], [], []
    for ln in vo.get('lines', []):
        fid = ln.get('file', ln['id']); p = os.path.join(vdir, f'{fid}.wav'); g = idx[ln['scene']]; s0 = starts[g] + float(ln.get('at', 0))
        if not os.path.exists(p): missing.append(ln['id']); continue
        a = read_wav(p); d = len(a) / sound.SR; voice.append((s0, a, ln['id'], g))
        timeline_vo.append(dict(id=ln['id'], file=fid, scene=ln['scene'], start=round(s0, 2), end=round(s0 + d, 2)))
        caps += caption_chunks(ln.get('caption') or ln.get('text', ''), s0, d, int((plan.get('captions') or {}).get('words', 7)))
    if missing: warn.append(f"no voice file for lines {', '.join(missing)} (silent there)")
    voice.sort(key=lambda x: x[0])
    for (s1, a1, l1, _), (s2, _, l2, _) in zip(voice, voice[1:]):
        e1 = s1 + len(a1) / sound.SR
        if e1 > s2 - 0.15: warn.append(f'voice lines {l1} and {l2} ' + (f'overlap by {e1 - s2:.2f}s' if e1 > s2 else f'have only {s2 - e1:.2f}s between them') + f' (line {l2} starts at {s2:.2f}s)')
    for s0, a, l, g in voice:
        end = starts[g + 1] if g + 1 < len(starts) else total
        if s0 + len(a) / sound.SR > end + 0.05: warn.append(f'line {l} runs {s0 + len(a) / sound.SR - end:.2f}s past the end of its scene "{scenes[g]["id"]}"')
    caps.sort()
    if caps: write_srt(caps, stem + '.srt')
    cp = plan.get('captions') or {}
    if cp.get('burn') and caps:  # in their own strip, so they cover nothing; the cover frame stays whole
        seq = burn_captions(seq, caps, fps, os.path.join(root, '.render', name, '_captions'), float(cp.get('strip', 0.14)), plan['background'], ext, bool(cimg), cp.get('place', 'bottom'))
        warn.append("the subtitles are burned in: turn the platform's automatic subtitles off, or they show twice")
    lst = os.path.join(root, '.render', f'{name}-frames.txt')
    with open(lst, 'w') as f:
        for p in seq: f.write(f"file '{p.replace(os.sep, '/')}'\nduration {1 / fps:.6f}\n")
    video = os.path.join(root, '.render', f'{name}-picture.mp4'); W, H = prof['width'], prof['height']
    vf = f"scale={W}:{H}:force_original_aspect_ratio=decrease:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={plan['background'].replace('#', '0x')},fps={fps},format=yuv420p"
    src = ['-f', 'concat', '-safe', '0', '-i', lst, '-vf', vf]
    if prof.get('encoder') == 'fast':
        try: C.run(ff, '-y', '-loglevel', 'error', *src, '-c:v', 'h264_nvenc', '-preset', 'p5', '-rc', 'vbr', '-cq', '28', '-b:v', '0', '-movflags', '+faststart', video)
        except subprocess.CalledProcessError:
            print('no GPU encoder here, encoding on the CPU', flush=True)
            C.run(ff, '-y', '-loglevel', 'error', *src, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '28', '-tune', 'animation', '-movflags', '+faststart', video)
    else:
        C.run(ff, '-y', '-loglevel', 'error', *src, '-c:v', 'libx264', '-preset', 'slow', '-crf', str(prof.get('crf', 23)), '-tune', 'animation', '-movflags', '+faststart', video)
    t_video = time.time()
    # the sound: the voice, the scenes' cues, a transition cue if the plan asks, the music
    cues = [(starts[i] + t, k) for i, m in enumerate(meta) for t, k in m['cues']]
    tsound = tr.get('sound')  # none unless the plan names one: a cue at every scene change adds up to noise
    cues += [(starts[i + 1] - 0.05, tsound) for i, (kind, K) in enumerate(kinds) if K and tsound]
    m = plan.get('music')
    moods = [(starts[idx[x['scene']]] + float(x.get('at', 0)), x['mood']) for x in m] if isinstance(m, list) else [(0.0, 'silent')]
    audio = sound.mix(total, cues, [(s, a) for s, a, _, _ in voice], moods, plan.get('sfx_swap'))
    track = music_track(plan, total, ff)
    if track is not None:  # the user's chosen track instead of the synthesized one, ducked under the voice the same way
        audio = audio + duck(track, [(s, a) for s, a, _, _ in voice], len(audio))
    aw = os.path.join(root, '.render', f'{name}-audio.wav'); write_wav(aw, audio / max(1.0, np.abs(audio).max() / 0.95))
    final = stem + '.mp4'; target = plan.get('loudness', -16)
    C.run(ff, '-y', '-loglevel', 'error', '-i', video, '-i', aw, '-c:v', 'copy', '-af', f'loudnorm=I={target}:TP=-1.5:LRA=11', '-ar', '48000',
          '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', final)
    if cimg:  # the cover inside the file too, and as a picture for the platform's custom thumbnail
        jpg = stem + '-cover.jpg'; Image.open(cimg).convert('RGB').resize((W, H), Image.LANCZOS).save(jpg, quality=92)
        embed_cover(ff, final, jpg)
    t_end = time.time()
    sheet(seq, bounds, fps, stem + '-transitions.png', labels)
    json.dump(dict(total=round(total, 2), scenes=[dict(id=s['id'], start=round(starts[i], 2), secs=round(meta[i]['secs'], 2)) for i, s in enumerate(scenes)],
                   voice=timeline_vo, cues=[dict(t=round(t, 2), kind=k) for t, k in sorted(cues, key=lambda c: c[0])]), open(stem + '-timeline.json', 'w'), indent=1)
    mb = os.path.getsize(final) / 1e6; lufs = loudness(ff, final)
    if cap and mb > cap: warn.append(f'{mb:.1f} MB is over the cap of {cap} MB')
    print(f'\n{final}\n  {int(total // 60)}:{total % 60:04.1f}, {W}x{H}, {fps} fps, {mb:.2f} MB, loudness {lufs} LUFS (target {target})')
    print(f'  time: frames {t_render - t_start:.0f} s, picture {t_video - t_render:.0f} s, sound and mux {t_end - t_video:.0f} s')
    for i, s in enumerate(scenes): print(f'  {int(starts[i] // 60)}:{starts[i] % 60:04.1f}  +{meta[i]["secs"]:.1f}s  {s["id"]}')
    made = [stem + x for x in ('-transitions.png', '-timeline.json', '.srt', '-cover.jpg') if os.path.exists(stem + x)]
    print('  also: ' + ', '.join(os.path.basename(x) for x in made) + (f'; the earlier build is in {moved}' if moved else ''))
    for w_ in warn: print('  ! ' + w_)


if __name__ == '__main__':
    main()
