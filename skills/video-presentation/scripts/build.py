"""Builds a video from a project's plan.json: renders the scenes frame by frame in parallel headless browsers (only the
scenes whose page, kit or settings changed since their last render), joins them, lays the voice, the scenes' sound cues
and the music under them, encodes, and writes what to check: a sheet of frames around every transition and a timeline.
Usage: build.py <plan.json> [--draft | --final | --profile <name>] [--browsers N] [--frames-only] [--force]
  --draft  480p, fewer frames a second, JPEG frames, the fastest encoder there is (a GPU one when present)
  --final  1080p, full frame rate, PNG frames, the quality encoder (the default)
Writes <project>/out/<name>-<profile>-<height>p.mp4, ...-transitions.png and ...-timeline.json."""
import json, os, subprocess, sys, time, wave
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from urllib.parse import quote
import numpy as np
from PIL import Image, ImageDraw
import common as C
import sound

ARGS = sys.argv[1:]


def arg(name, default=None):
    return ARGS[ARGS.index(name) + 1] if name in ARGS else default


def scene_url(base, s):
    extra = ''
    if s.get('tag'): extra = f"tag={quote(s['tag'])}&tone={s.get('tone', 'bad')}" + (f"&tagin={s['tagin']}" if 'tagin' in s else '')
    return C.page_url(base, s['page'], extra)


def jobs_for(plan, prof, force):
    jobs = []
    for s in plan['scenes']:
        key = C.content_key(plan, s['page'], s.get('tag'), s.get('tone'), s['from'], s['to'], s.get('speed', 1), prof['fps'], prof['scale'], prof['format'], plan['scheme'], plan['stage'])
        d = os.path.join(plan['_root'], '.render', prof['name'], s['id']); mp = os.path.join(d, 'meta.json')
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


def loudness(ff, path):
    r = subprocess.run([ff, '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128=framelog=quiet', '-f', 'null', '-'], capture_output=True, text=True, errors='replace')
    for line in reversed(r.stderr.splitlines()):
        if line.strip().startswith('I:'): return float(line.split()[1])
    return None


def main():
    plan = C.load_plan(ARGS[0]); root = plan['_root']
    name = arg('--profile') or ('draft' if '--draft' in ARGS else 'final')
    prof = C.profile(plan, name); ext = 'jpg' if prof['format'] == 'jpeg' else 'png'
    frames_only = '--frames-only' in ARGS or name == 'gif'
    t_start = time.time()
    jobs = jobs_for(plan, prof, '--force' in ARGS); todo = [j for j in jobs if not j['cached']]
    nb = int(arg('--browsers', C.default_browsers(len(todo))))
    print(f'{len(todo)} of {len(jobs)} scenes to render ({name}, {prof["fps"]} fps, {prof["height"]}p), {min(nb, max(1, len(todo)))} browsers', flush=True)
    if todo: render(plan, prof, todo, min(nb, len(todo)))
    t_render = time.time()
    scenes = plan['scenes']; dirs = {j['scene']['id']: j['dir'] for j in jobs}
    if frames_only:
        for s in scenes: print(dirs[s['id']])
        print(f'frames in {t_render - t_start:.0f} s'); return
    fps = prof['fps']; ff = C.ffmpeg()
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
    os.makedirs(os.path.join(root, 'out'), exist_ok=True)
    stem = os.path.join(root, 'out', f"{plan['name']}-{name}-{prof['height']}p")
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
    # the sound: the voice lines where the plan puts them, the scenes' cues, a soft cue at each transition, the music
    idx = {s['id']: i for i, s in enumerate(scenes)}
    vo = plan.get('voice') or {}; vdir = os.path.join(root, vo.get('dir', 'voice')); voice, missing, timeline_vo = [], [], []
    for ln in vo.get('lines', []):
        p = os.path.join(vdir, f"{ln['id']}.wav"); g = idx[ln['scene']]; s0 = starts[g] + float(ln.get('at', 0))
        if not os.path.exists(p): missing.append(ln['id']); continue
        a = read_wav(p); voice.append((s0, a, ln['id'], g)); timeline_vo.append(dict(id=ln['id'], scene=ln['scene'], start=round(s0, 2), end=round(s0 + len(a) / sound.SR, 2)))
    warn = []
    if missing: warn.append(f"no voice file for lines {', '.join(missing)} (silent there)")
    voice.sort(key=lambda x: x[0])
    for (s1, a1, l1, _), (s2, _, l2, _) in zip(voice, voice[1:]):
        e1 = s1 + len(a1) / sound.SR
        if e1 > s2 - 0.15: warn.append(f'voice lines {l1} and {l2} ' + (f'overlap by {e1 - s2:.2f}s' if e1 > s2 else f'have only {s2 - e1:.2f}s between them') + f' (line {l2} starts at {s2:.2f}s)')
    for s0, a, l, g in voice:
        end = starts[g + 1] if g + 1 < len(starts) else total
        if s0 + len(a) / sound.SR > end + 0.05: warn.append(f'line {l} runs {s0 + len(a) / sound.SR - end:.2f}s past the end of its scene "{scenes[g]["id"]}"')
    cues = [(starts[i] + t, k) for i, m in enumerate(meta) for t, k in m['cues']]
    tsound = tr.get('sound', 'swipe')
    cues += [(starts[i + 1] - 0.05, tsound) for i, (kind, K) in enumerate(kinds) if K and tsound]
    m = plan.get('music')
    moods = [(starts[idx[x['scene']]] + float(x.get('at', 0)), x['mood']) for x in m] if isinstance(m, list) else [(0.0, 'silent')]
    audio = sound.mix(total, cues, [(s, a) for s, a, _, _ in voice], moods, plan.get('sfx_swap'))
    track = music_track(plan, total, ff)
    if track is not None:  # the user's chosen track instead of the synthesized one, ducked under the voice the same way
        v = np.zeros(len(audio))
        for s, a, _, _ in voice: i = int(sound.SR * s); a = a[: max(0, len(v) - i)]; v[i:i + len(a)] += np.abs(a)
        w = int(sound.SR * 0.25); c = np.concatenate([[0.0], np.cumsum(v)]); ii = np.arange(len(v))
        e = (c[np.clip(ii + w // 2, 0, len(v))] - c[np.clip(ii - w // 2, 0, len(v))]) / w; e = np.clip(e / (e.max() + 1e-9) * 6, 0, 1)
        audio = audio + track[: len(audio)] * (1 - 0.6 * e)[: len(track), None]
    aw = os.path.join(root, '.render', f'{name}-audio.wav'); write_wav(aw, audio / max(1.0, np.abs(audio).max() / 0.95))
    final = stem + '.mp4'; target = plan.get('loudness', -16)
    C.run(ff, '-y', '-loglevel', 'error', '-i', video, '-i', aw, '-c:v', 'copy', '-af', f'loudnorm=I={target}:TP=-1.5:LRA=11', '-ar', '48000',
          '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', final)
    t_end = time.time()
    labels = [f'{scenes[i]["id"]} -> {scenes[i + 1]["id"]}  ({kinds[i][0]})' for i in range(len(kinds))]
    sheet(seq, bounds, fps, stem + '-transitions.png', labels)
    json.dump(dict(total=round(total, 2), scenes=[dict(id=s['id'], start=round(starts[i], 2), secs=round(meta[i]['secs'], 2)) for i, s in enumerate(scenes)],
                   voice=timeline_vo, cues=[dict(t=round(t, 2), kind=k) for t, k in sorted(cues, key=lambda c: c[0])]), open(stem + '-timeline.json', 'w'), indent=1)
    mb = os.path.getsize(final) / 1e6; lufs = loudness(ff, final)
    if plan.get('max_mb') and mb > plan['max_mb']: warn.append(f'{mb:.1f} MB is over the limit of {plan["max_mb"]} MB')
    print(f'\n{final}\n  {int(total // 60)}:{total % 60:04.1f}, {W}x{H}, {fps} fps, {mb:.2f} MB, loudness {lufs} LUFS (target {target})')
    print(f'  time: frames {t_render - t_start:.0f} s, picture {t_video - t_render:.0f} s, sound and mux {t_end - t_video:.0f} s')
    for i, s in enumerate(scenes): print(f'  {int(starts[i] // 60)}:{starts[i] % 60:04.1f}  +{meta[i]["secs"]:.1f}s  {s["id"]}')
    print(f'  check: {stem}-transitions.png (frames around every transition), {stem}-timeline.json')
    for w_ in warn: print('  ! ' + w_)


if __name__ == '__main__':
    main()
