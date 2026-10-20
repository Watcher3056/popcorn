"""A listening sample for a sound change, before anything re-renders: the same moments of an already built video, first
with its current sound, then with each candidate, one after another, each labelled on screen.
Usage: sound_sample.py <plan.json> --ranges 12.0-17.5,40-44 --try "A · soft rising tone" swipe=glide [--try ...]
       [--profile draft|final]   a candidate is a label and its swaps of cue kinds (from=to, comma-separated; from= mutes)
Writes <project>/out/<name>-sound-sample.mp4."""
import json, os, sys
import numpy as np
import common as C
import sound
from build import read_wav, write_wav, music_track, keep_previous

ARGS = sys.argv[1:]
plan = C.variant(C.load_plan(ARGS[0]), ARGS[ARGS.index('--variant') + 1] if '--variant' in ARGS else None); root = plan['_root']; C.lock(plan)
name = ARGS[ARGS.index('--profile') + 1] if '--profile' in ARGS else 'final'
prof = C.profile(plan, name); stem = os.path.join(root, 'out', f"{plan['name']}-{name}-{prof['short']}p")
tl = json.load(open(stem + '-timeline.json')); total = tl['total']; ff = C.ffmpeg()
ranges = [tuple(map(float, r.split('-'))) for r in ARGS[ARGS.index('--ranges') + 1].split(',')]
cands = [('NOW · current sound', {})]
for i, a in enumerate(ARGS):
    if a == '--try':
        label, sw = ARGS[i + 1], ARGS[i + 2]
        cands.append((label, {k: (v or None) for k, v in (p.split('=') for p in sw.split(',') if '=' in p)}))
starts = {s['id']: s['start'] for s in tl['scenes']}
vdir = os.path.join(root, (plan.get('voice') or {}).get('dir', 'voice'))
voice = [(v['start'], read_wav(os.path.join(vdir, f"{v.get('file', v['id'])}.wav"))) for v in tl['voice']]
cues = [(c['t'], c['kind']) for c in tl['cues']]
m = plan.get('music')
moods = [(starts[x['scene']] + float(x.get('at', 0)), x['mood']) for x in m] if isinstance(m, list) else [(0.0, 'silent')]
track = music_track(plan, total, ff)
tmp = os.path.join(root, '.render', 'sound-sample'); os.makedirs(tmp, exist_ok=True)
font = C.font_file(True); clips = []
for k, (label, swap) in enumerate(cands):
    a = sound.mix(total, [(t, swap.get(kd, kd)) for t, kd in cues], voice, moods, plan.get('sfx_swap'))
    if track is not None: a = a + track[: len(a)]
    aw = os.path.join(tmp, f'a{k}.wav'); write_wav(aw, a / max(1.0, np.abs(a).max() / 0.95))
    for j, (t0, t1) in enumerate(ranges):
        c = os.path.join(tmp, f'c{k}-{j}.mp4'); txt = label.replace(':', '\\:').replace("'", '')
        fc = (f"[1:a]loudnorm=I={plan.get('loudness', -16)}:TP=-1.5:LRA=11,aresample=48000,atrim=start={t0}:end={t1},asetpts=PTS-STARTPTS,"
              f"afade=t=in:d=0.08,afade=t=out:st={t1 - t0 - 0.12}:d=0.12[a];[0:v]trim=start={t0}:end={t1},setpts=PTS-STARTPTS,"
              f"drawtext=fontfile='{font}':text='{txt}':x=(w-tw)/2:y=h*0.06:fontsize=h*0.045:fontcolor=white:box=1:boxcolor=0x12151a@0.82:boxborderw=14[v]")
        C.run(ff, '-y', '-loglevel', 'error', '-i', stem + '.mp4', '-i', aw, '-filter_complex', fc, '-map', '[v]', '-map', '[a]',
              '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-c:a', 'aac', '-b:a', '192k', c)
        clips.append(c)
lst = os.path.join(tmp, 'list.txt'); open(lst, 'w').write(''.join(f"file '{c.replace(os.sep, '/')}'\n" for c in clips))
out = os.path.join(root, 'out', f"{plan['name']}-sound-sample.mp4"); keep_previous(out[:-4])  # an earlier sample stays, in out/old/
C.run(ff, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', out)
print(out, f'{sum(t1 - t0 for t0, t1 in ranges) * len(cands):.1f} s:', ' / '.join(l for l, _ in cands))
