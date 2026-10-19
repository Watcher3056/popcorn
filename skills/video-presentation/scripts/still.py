"""One still image of a page at a size of its own: a thumbnail, a cover, a social card, a check of one moment.
Usage: still.py <plan.json> <page> <t ms> <out.png> [--css 1280x720] [--px 1920x1080]
  --css: the page's own size in CSS pixels (default: the plan's stage); --px: the image size (default: 2x the CSS size)
The page is served from the project like a scene, so it can use the kit and the scenes' files."""
import json, os, sys
import common as C

ARGS = sys.argv[1:]
arg = lambda n, d=None: ARGS[ARGS.index(n) + 1] if n in ARGS else d
plan = C.load_plan(ARGS[0]); page, t, out = ARGS[1], float(ARGS[2]), os.path.abspath(ARGS[3])
cw, ch = map(int, (arg('--css') or f"{plan['stage'][0]}x{plan['stage'][1]}").split('x'))
pw, ph = map(int, (arg('--px') or f'{cw * 2}x{ch * 2}').split('x'))
os.makedirs(os.path.dirname(out), exist_ok=True)
with C.server(plan) as base, C.browsers(plan, 1) as ports:
    jf = os.path.join(plan['_root'], '.render', 'still-job.json')
    json.dump([dict(url=C.page_url(base, page), t=t, out=out, width=cw, height=ch, scale=pw / cw, scheme=plan['scheme'])], open(jf, 'w'))
    C.run('node', os.path.join(C.HERE, 'stills.mjs'), jf, env=dict(os.environ, CDP_PORT=str(ports[0])))
