"""The storyboard for the user's approval before any video: real frames rendered from the scene pages (the frames the
video will have, not sketches), each scene's beats left to right in time, what happens on screen, its voice lines, its
length, and whether it is new, changed or kept.
Usage: storyboard.py <plan.json> [--only new,changed] [--rows 5] [--browsers N] [--variant <name>]
Each scene in the plan gives "board": [page times in ms] (default: its middle), "name", "screen" and "status".
Writes <project>/out/<name>-storyboard-<n>.png."""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw
import common as C
from build import scene_url, keep_previous

ARGS = sys.argv[1:]
arg = lambda n, d=None: ARGS[ARGS.index(n) + 1] if n in ARGS else d
STATUS = {'new': ((18, 161, 80), (231, 246, 236)), 'changed': ((194, 120, 3), (255, 244, 220)), 'kept': ((107, 114, 128), (238, 240, 243))}
PAGE_W, PAD, GAP = 1800, 28, 34


def main():
    plan = C.variant(C.load_plan(ARGS[0]), arg('--variant')); root = plan['_root']; prof = C.profile(plan, 'board'); C.lock(plan)
    only = set(arg('--only').split(',')) if arg('--only') else None
    cover = plan.get('cover'); everything = list(plan['scenes'])
    if cover:  # a feed piece's cover is approved with its scenes: it is frame 0 and the thumbnail
        cs = dict(id='_cover', name='Cover: frame 0 and the thumbnail', page=cover.get('page') or '', board=[cover.get('t', 0)], status=cover.get('status', 'new'),
                  screen='What the feed and the player show before play.', **{'from': 0, 'to': 0})
        everything = [cs] + everything
    scenes = [s for s in everything if not only or s.get('status', 'new') in only]
    if not scenes: raise SystemExit('no scenes to show')
    out_dir = os.path.join(root, '.render', 'board'); os.makedirs(out_dir, exist_ok=True)
    jobs, frames = [], {}
    with C.server(plan) as base:
        for s in scenes:
            if s['id'] == '_cover' and cover.get('image'): frames['_cover'] = [os.path.join(root, cover['image'])]; continue
            ts = s.get('board') or [(s['from'] + s['to']) / 2]
            frames[s['id']] = []
            for k, t in enumerate(ts):
                f = os.path.join(out_dir, f"{s['id']}-{k}.png"); frames[s['id']].append(f)
                jobs.append(dict(url=scene_url(base, s), t=t, out=f, width=plan['stage'][0], height=plan['stage'][1], scale=prof['scale'], scheme=plan['scheme']))
        n = max(1, min(int(arg('--browsers', C.default_browsers(len(scenes)))), len({j['url'] for j in jobs})))
        groups = [[] for _ in range(n)]
        by_url = {}
        for j in jobs: by_url.setdefault(j['url'], []).append(j)
        for k, js in enumerate(by_url.values()): groups[k % n] += js  # one page's frames stay in one browser
        with C.browsers(plan, n) as ports:
            def one(a):
                port, js = a; jf = os.path.join(out_dir, f'jobs-{port}.json'); json.dump(js, open(jf, 'w'))
                C.run('node', os.path.join(C.HERE, 'stills.mjs'), jf, env=dict(os.environ, CDP_PORT=str(port)), stdout=open(os.devnull, 'w'))
            list(ThreadPoolExecutor(n).map(one, [(p, g) for p, g in zip(ports, groups) if g]))
    lines = {}
    for ln in (plan.get('voice') or {}).get('lines', []): lines.setdefault(ln['scene'], []).append(ln.get('text', ''))
    rows = int(arg('--rows', 5)); pages = [scenes[i:i + rows] for i in range(0, len(scenes), rows)]
    total = sum(C.scene_secs(s) for s in plan['scenes'])
    outs = []; os.makedirs(os.path.join(root, 'out'), exist_ok=True)
    moved = keep_previous(os.path.join(root, 'out', f"{plan['name']}-storyboard-"))  # an earlier storyboard stays, in out/old/
    for pi, part in enumerate(pages, 1):
        head = f"{plan['name']} · storyboard · {pi} of {len(pages)} · ~{int(total // 60)}:{total % 60:02.0f} in all" + (f" · only {', '.join(sorted(only))}" if only else '')
        outs.append(page(part, frames, lines, head, os.path.join(root, 'out', f"{plan['name']}-storyboard-{pi}.png"), everything))
    for o in outs: print(o)
    if moved: print('the earlier storyboard is in', moved)


def wrap(d, text, font, width):
    words, out, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if d.textlength(t, font=font) <= width: cur = t
        else: out.append(cur); cur = w
    return out + ([cur] if cur else [])


def page(part, frames, lines, head, path, all_scenes):
    H1, B, R, I, P = C.font(32, True), C.font(22, True), C.font(20), C.font(21, italic=True), C.font(15, True)
    tmp = Image.new('RGB', (10, 10)); dm = ImageDraw.Draw(tmp); tw = PAGE_W - 2 * PAD
    blocks = []
    for s in part:
        fs = frames[s['id']]; k = len(fs)
        fw = min(820, (tw - (k - 1) * GAP) // k); ims = []
        for f in fs:
            im = Image.open(f).convert('RGB'); ims.append(im.resize((fw, round(im.height * fw / im.width)), Image.LANCZOS))
        scr = wrap(dm, s.get('screen', ''), R, tw); vo = wrap(dm, ' / '.join(lines.get(s['id'], [])) and '“' + ' / '.join(lines.get(s['id'], [])) + '”', I, tw)
        h = 44 + ims[0].height + 16 + (30 + 27 * len(scr) if scr else 0) + (34 + 28 * len(vo) if vo else 0) + 26
        blocks.append((s, ims, scr, vo, h))
    img = Image.new('RGB', (PAGE_W, 90 + sum(b[4] for b in blocks)), (245, 246, 248)); d = ImageDraw.Draw(img)
    d.text((PAD, 26), head, font=H1, fill=(18, 21, 26)); y = 90
    for s, ims, scr, vo, h in blocks:
        n = all_scenes.index(s) + 1; st = s.get('status', 'new'); fg, bg = STATUS.get(st, STATUS['new'])
        lw = d.textlength(st.upper(), font=P) + 20
        d.rounded_rectangle([PAD, y + 3, PAD + lw, y + 27], 8, fill=bg); d.text((PAD + 10, y + 5), st.upper(), font=P, fill=fg)
        d.text((PAD + lw + 12, y), f"{n:02d}  {s.get('name', s['id'])}" + (f"   ~{C.scene_secs(s):.1f} s" if C.scene_secs(s) else ''), font=B, fill=(18, 21, 26))
        fy = y + 44; x = PAD
        for k, im in enumerate(ims):
            img.paste(im, (x, fy)); d.rectangle([x - 1, fy - 1, x + im.width, fy + im.height], outline=(214, 218, 224))
            if k < len(ims) - 1:  # an arrow drawn, not typed: some fonts have no arrow glyph
                ax, ay = x + im.width + GAP // 2, fy + im.height // 2
                d.polygon([(ax - 7, ay - 9), (ax + 7, ay), (ax - 7, ay + 9)], fill=(150, 156, 166))
            x += im.width + GAP
        ty = fy + ims[0].height + 16
        if scr:
            d.text((PAD, ty), 'On screen', font=B, fill=(107, 114, 128)); ty += 30
            for line in scr: d.text((PAD, ty), line, font=R, fill=(40, 44, 52)); ty += 27
        if vo:
            ty += 4; d.text((PAD, ty), 'Voice', font=B, fill=(18, 161, 80)); ty += 30
            for line in vo: d.text((PAD, ty), line, font=I, fill=(18, 21, 26)); ty += 28
        y += h
    img.save(path); return path


if __name__ == '__main__':
    main()
