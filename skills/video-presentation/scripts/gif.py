"""Rendered frames -> an animated GIF at their frame rate, through ffmpeg's two-pass palette: one palette made from all
frames, so small dark text and rare colours (a red mark seen for a second) keep their colour.
Usage: gif.py <out.gif> <framesDir> [<framesDir> ...] [--width 800] [--colors 192]
Frames come from build.py --profile gif (or --frames-only); several dirs play one after another."""
import argparse, json, os
import common as C

ap = argparse.ArgumentParser()
ap.add_argument('out'); ap.add_argument('dirs', nargs='+')
ap.add_argument('--width', type=int, default=800); ap.add_argument('--colors', type=int, default=192)
a = ap.parse_args()
lst = os.path.splitext(os.path.abspath(a.out))[0] + '.frames.txt'; fps = None
with open(lst, 'w') as f:
    for d in a.dirs:
        meta = json.load(open(os.path.join(d, 'meta.json'))); fps = fps or meta['fps']
        for i in range(meta['frames']):
            p = os.path.abspath(os.path.join(d, f"{i:05d}.{meta.get('ext', 'png')}")).replace(os.sep, '/')
            f.write(f"file '{p}'\nduration {1 / meta['fps']:.6f}\n")
vf = (f"fps={fps},scale={a.width}:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors={a.colors}:stats_mode=full[p];"
      f"[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle")
C.run(C.ffmpeg(), '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-filter_complex', vf, '-loop', '0', a.out)
os.remove(lst)
print(a.out, round(os.path.getsize(a.out) / 1e6, 2), 'MB')
