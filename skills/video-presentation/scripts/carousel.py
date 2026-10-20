"""A carousel (a document post of slides people swipe in a feed): each scene of the plan becomes one slide, its page as it
stands at the scene's last "board" time (default: its "to"), and the slides go into one PDF. With them come two sheets to check before sending: all
slides side by side, and all slides at the width a phone shows them, where small text stops reading.
Usage: carousel.py <plan.json> [--px 1080x1350] [--phone 390] [--variant <name>]
  --px: the slide's size in pixels, in the stage's shape (default: twice the stage, e.g. a [540, 675] stage gives 1080x1350,
  the 4:5 shape); the slide's shape comes from the stage
Writes <project>/out/<name>-carousel.pdf, ...-carousel-<n>.png, ...-carousel-sheet.png and ...-carousel-phone.png;
an earlier carousel moves to out/old/<time>/."""
import os, sys
from PIL import Image, ImageDraw
import common as C
from build import keep_previous, scene_query

ARGS = sys.argv[1:]
arg = lambda n, d=None: ARGS[ARGS.index(n) + 1] if n in ARGS else d


def grid(ims, cols, gap, path, label=None):
    rows = (len(ims) + cols - 1) // cols; w, h = ims[0].size
    top = 46 if label else gap
    g = Image.new('RGB', (gap + cols * (w + gap), top + rows * (h + gap + 22)), (245, 246, 248)); d = ImageDraw.Draw(g); f = C.font(16, True)
    if label: d.text((gap, 14), label, font=f, fill=(18, 21, 26))
    for k, im in enumerate(ims):
        x, y = gap + (k % cols) * (w + gap), top + (k // cols) * (h + gap + 22)
        g.paste(im, (x, y)); d.rectangle([x - 1, y - 1, x + w, y + h], outline=(214, 218, 224)); d.text((x, y + h + 3), f'{k + 1} / {len(ims)}', font=f, fill=(107, 114, 128))
    g.save(path)


def main():
    plan = C.variant(C.load_plan(ARGS[0]), arg('--variant')); root = plan['_root']; sw, sh = plan['stage']; C.lock(plan)
    pw, ph = map(int, (arg('--px') or f'{sw * 2}x{sh * 2}').split('x'))
    if abs(pw / ph - sw / sh) > 0.01:
        raise SystemExit(f'--px {pw}x{ph} is not the shape of the stage {sw}x{sh}: set the plan\'s "stage" to the slide\'s shape (e.g. [540, 675] for 4:5)')
    slides = plan['scenes']
    if not slides: raise SystemExit('plan.json has no scenes: each scene is one slide')
    out = os.path.join(root, 'out'); os.makedirs(out, exist_ok=True)
    stem = os.path.join(out, f"{plan['name']}-carousel"); moved = keep_previous(stem)
    tmp = os.path.join(root, '.render', 'carousel'); os.makedirs(tmp, exist_ok=True)
    page = lambda s: s['page'] + (('&' if '?' in s['page'] else '?') + scene_query(s) if s.get('tag') else '')  # with its corner label
    jobs = [dict(page=page(s), t=(s.get('board') or [s['to']])[-1], out=os.path.join(tmp, f'{k + 1:02d}.png'), width=sw, height=sh, scale=pw / sw)
            for k, s in enumerate(slides)]
    C.stills(plan, jobs)
    ims = [Image.open(j['out']).convert('RGB') for j in jobs]
    for k, im in enumerate(ims): im.save(f'{stem}-{k + 1:02d}.png')
    ims[0].save(stem + '.pdf', save_all=True, append_images=ims[1:], resolution=144)
    small = [im.resize((360, round(im.height * 360 / im.width)), Image.LANCZOS) for im in ims]
    grid(small, min(6, len(small)), 18, stem + '-sheet.png', f"{plan['name']} carousel · {len(ims)} slides · {pw}x{ph}")
    phone = int(arg('--phone', 390))
    at_phone = [im.resize((phone, round(im.height * phone / im.width)), Image.LANCZOS) for im in ims]
    grid(at_phone, min(4, len(at_phone)), 24, stem + '-phone.png', f'at a phone width ({phone} px): every word that matters must still read')
    mb = os.path.getsize(stem + '.pdf') / 1e6
    print(f'{stem}.pdf\n  {len(ims)} slides, {pw}x{ph}, {mb:.1f} MB')
    print(f'  check: {os.path.basename(stem)}-sheet.png (all slides), {os.path.basename(stem)}-phone.png (at a phone width)' + (f'; the earlier carousel is in {moved}' if moved else ''))
    cap = plan.get('max_mb')
    if cap and mb > cap: print(f'  ! {mb:.1f} MB is over the cap of {cap} MB')


if __name__ == '__main__':
    main()
