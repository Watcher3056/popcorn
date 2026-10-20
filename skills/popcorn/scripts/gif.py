"""Rendered frames -> an animated GIF at their frame rate, through ffmpeg's two-pass palette: one palette made from all
frames, so small dark text and rare colours (a red mark seen for a second) keep their colour.
build.py --profile gif (or gif-draft) makes the GIF from the whole plan, transitions included. By hand:
Usage: gif.py <out.gif> <framesDir> [<framesDir> ...] [--width 800] [--colors 192]   (several dirs play one after another)"""
import argparse, json, os
import common as C


def make_gif(frames, fps, out, width, colors=192):
    """frames: image paths in order, each shown 1/fps; returns the GIF's size in MB"""
    lst = os.path.splitext(os.path.abspath(out))[0] + '.frames.txt'
    with open(lst, 'w') as f:
        for p in frames: f.write(f"file '{os.path.abspath(p).replace(os.sep, '/')}'\nduration {1 / fps:.6f}\n")
    vf = (f"fps={fps},scale={width}:-2:flags=lanczos,split[a][b];[a]palettegen=max_colors={colors}:stats_mode=full[p];"
          f"[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle")
    C.run(C.ffmpeg(), '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-filter_complex', vf, '-loop', '0', out)
    os.remove(lst)
    return os.path.getsize(out) / 1e6


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('dirs', nargs='+')
    ap.add_argument('--width', type=int, default=800); ap.add_argument('--colors', type=int, default=192)
    a = ap.parse_args()
    frames, fps = [], None
    for d in a.dirs:
        meta = json.load(open(os.path.join(d, 'meta.json'))); fps = fps or meta['fps']
        frames += [os.path.join(d, f"{i:05d}.{meta.get('ext', 'png')}") for i in range(meta['frames'])]
    print(a.out, round(make_gif(frames, fps, a.out, a.width, a.colors), 2), 'MB')
