"""Readies the narration for build.py, whatever made it (a TTS model, a recording of the user, etc.): trims the silence
at both ends, converts to 48 kHz mono, measures each take's pace and keeps one take per line.
A TTS take that drops the end of its line comes out too fast for its words: a take far faster than the line's other
takes is skipped, and a line with one take far faster than the other lines is flagged for a retake.
Usage: voice_prep.py <plan.json> <rawDir>   raw files: <id>.<ext> or <id>-<anything>.<ext> (several takes), any
format ffmpeg reads. Writes <project>/<voice.dir>/<id>.wav and prints a table to check."""
import glob, os, shutil, subprocess, sys, wave
import common as C

plan = C.load_plan(sys.argv[1]); raw = os.path.abspath(sys.argv[2]); ff = C.ffmpeg()
vo = plan.get('voice') or {}; out = os.path.join(plan['_root'], vo.get('dir', 'voice')); os.makedirs(out, exist_ok=True)
tmp = os.path.join(plan['_root'], '.render', 'takes'); os.makedirs(tmp, exist_ok=True)
TRIM = 'silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse'
rows = []
for ln in vo.get('lines', []):
    lid, words = ln['id'], max(1, len(ln.get('text', '').split()))
    srcs = sorted(f for f in glob.glob(os.path.join(raw, f'{lid}.*')) + glob.glob(os.path.join(raw, f'{lid}-*')) if os.path.isfile(f))
    if not srcs: rows.append((lid, None, 'no take', ln.get('text', ''))); continue
    takes = []
    for k, s in enumerate(srcs):
        dst = os.path.join(tmp, f'{lid}-{k}.wav')
        C.run(ff, '-y', '-loglevel', 'error', '-i', s, '-af', TRIM, '-ar', '48000', '-ac', '1', '-sample_fmt', 's16', dst)
        with wave.open(dst) as w: d = w.getnframes() / w.getframerate()
        takes.append((words / max(d, 0.05), d, dst, os.path.basename(s)))
    paces = sorted(p for p, *_ in takes); med = paces[len(paces) // 2]
    ok = [t for t in takes if t[0] <= med * 1.12] or takes
    keep = min(ok, key=lambda t: t[0])
    shutil.copyfile(keep[2], os.path.join(out, f'{lid}.wav'))
    rows.append((lid, keep, ' '.join(f'{p:.2f}' for p, *_ in takes), ln.get('text', '')))
kept = [r[1][0] for r in rows if r[1]]
med_all = sorted(kept)[len(kept) // 2] if kept else 0
print(f'{"line":>5}  {"secs":>5}  {"words/s":>7}  takes (words/s)  kept      text')
for lid, keep, paces, text in rows:
    if not keep: print(f'{lid:>5}  {"-":>5}  {"-":>7}  {paces}  {text[:60]}'); continue
    flag = '  ! much faster than the other lines: listen, maybe retake (cut short?)' if med_all and keep[0] > med_all * 1.3 else ''
    print(f'{lid:>5}  {keep[1]:5.2f}  {keep[0]:7.2f}  {paces:<15}  {keep[3]:<8}  {text[:60]}{flag}')
print('->', out)
