"""Shared helpers for the toolkit: finding Chrome, ffmpeg and fonts, the local server and a pool of headless browsers.
Every tool takes the project's plan.json; the project folder holds the scene pages, and the kit is served under /kit/."""
import contextlib, functools, glob, hashlib, json, os, platform, shutil, socket, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = HERE  # kit.js and kit.css live next to the scripts; a project may override them with its own kit/ folder

PROFILES = {
    # Sizes name the picture's short side, so a vertical stage gets the same quality as a wide one (1080 → 1080x1920).
    # the storyboard's still frames: crisp enough to judge the look
    'board': dict(fps=0, short=720, format='png'),
    # the 480p check of rhythm, timing and sound: fewer frames, JPEG frames, the fastest encoder there is
    'draft': dict(fps=24, short=480, format='jpeg', encoder='fast'),
    # the approved cut in full quality
    'final': dict(fps=30, short=1080, format='png', encoder='quality'),
    # an animated GIF: its cheap preview is the GIF itself at 'gif-draft'
    'gif': dict(fps=20, short=540, format='png'),
    'gif-draft': dict(fps=12, short=300, format='png'),
}


def load_plan(path):
    with open(path, encoding='utf-8') as f: plan = json.load(f)
    plan['_root'] = os.path.dirname(os.path.abspath(path))
    plan.setdefault('name', os.path.basename(plan['_root']))
    plan.setdefault('stage', [960, 540])
    plan.setdefault('scheme', 'light')
    plan.setdefault('background', '#f5f6f8')
    plan.setdefault('scenes', [])
    ids = [s['id'] for s in plan['scenes']]
    if len(set(ids)) != len(ids): raise SystemExit('plan.json: scene ids repeat')
    return plan


def variant(plan, name):
    """one plan, several versions (with or without a part, etc.): "variants": {"<name>": {"drop": [scene ids],
    "drop_lines": [line ids], "lines": {"<line id>": {"file": "<other take>", "text": "..."}}}}; the unchanged scenes come
    from the cache"""
    if not name: return plan
    v = (plan.get('variants') or {}).get(name)
    if v is None: raise SystemExit(f'plan.json has no variant "{name}"')
    bad = set(v) - {'drop', 'drop_lines', 'lines', 'scenes'}
    if bad: raise SystemExit(f'variant "{name}": unknown keys {sorted(bad)}; a variant takes drop, drop_lines, lines and scenes')
    sids = {s['id'] for s in plan['scenes']}; vo = plan.get('voice') or {}; lids = {l['id'] for l in vo.get('lines', [])}
    wrong = (set(v.get('drop', [])) | set(v.get('scenes') or {})) - sids
    wrong_l = (set(v.get('drop_lines', [])) | set(v.get('lines') or {})) - lids
    if wrong or wrong_l: raise SystemExit(f'variant "{name}" names what the plan has not: scenes {sorted(wrong)}, lines {sorted(wrong_l)}')
    drop, drop_lines = set(v.get('drop', [])), set(v.get('drop_lines', []))
    # a scene that differs inside (another page, another range, etc.): its fields replaced; it renders on its own
    ov = v.get('scenes') or {}  # a changed scene keeps a cache of its own, so the versions don't overwrite each other's frames
    plan['scenes'] = [dict(s, **ov[s['id']], _cache=f"{s['id']}@{name}") if s['id'] in ov else s for s in plan['scenes'] if s['id'] not in drop]
    if vo:
        lines = [dict(l) for l in vo.get('lines', []) if l.get('scene') not in drop and l['id'] not in drop_lines]
        for l in lines: l.update((v.get('lines') or {}).get(l['id'], {}))
        vo['lines'] = lines
    if isinstance(plan.get('music'), list): plan['music'] = [m for m in plan['music'] if m['scene'] not in drop]
    plan['name'] = f"{plan['name']}-{name}"
    return plan


def stills(plan, jobs, n=None):
    """still frames of pages: jobs = [{page, t, out, width, height, scale}]; the frames of one page stay in one browser"""
    if not jobs: return
    groups = {}
    for j in jobs: groups.setdefault(j['page'], []).append(j)
    n = min(n or default_browsers(len(groups)), len(groups))
    with server(plan) as base, browsers(plan, n) as ports:
        lots = [[] for _ in ports]
        for k, js in enumerate(groups.values()):
            lots[k % len(ports)] += [dict(url=page_url(base, j['page']), t=j['t'], out=j['out'], width=j['width'], height=j['height'],
                                          scale=j['scale'], scheme=plan['scheme']) for j in js]
        tmp = os.path.join(plan['_root'], '.render'); os.makedirs(tmp, exist_ok=True)

        def one(a):
            port, lot = a; jf = os.path.join(tmp, f'stills-{port}.json')
            with open(jf, 'w') as f: json.dump(lot, f)
            run('node', os.path.join(HERE, 'stills.mjs'), jf, env=dict(os.environ, CDP_PORT=str(port)), stdout=subprocess.DEVNULL)
        from concurrent.futures import ThreadPoolExecutor
        list(ThreadPoolExecutor(len(ports)).map(one, [(p, l) for p, l in zip(ports, lots) if l]))


_LOCK = []


def lock(plan):
    """one build at a time per project: two would share the browsers' profiles and the files in .render/ and overwrite
    each other's; the lock goes with the process, so a crash leaves none behind"""
    d = os.path.join(plan['_root'], '.render'); os.makedirs(d, exist_ok=True)
    f = open(os.path.join(d, 'build.lock'), 'a+')
    try:
        if platform.system() == 'Windows':
            import msvcrt; f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl; fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit('another build of this project is running (a build, a storyboard, a carousel, etc.): '
                         'let it finish, then run this one; versions build one after another')
    _LOCK.append(f)


def disk_check(path, need_bytes, what):
    """frames take room: warn early, stop before the disk fills (nothing is deleted to make room; the user decides)"""
    free = shutil.disk_usage(path).free
    if free < need_bytes:
        raise SystemExit(f'not enough disk for {what}: {free / 1e9:.1f} GB free, about {need_bytes / 1e9:.1f} GB needed. '
                         'Free some space (old frames in .render/ can be rebuilt) and run again')
    if free < 2 * need_bytes + 1e9:
        print(f'  ! the disk is nearly full: {free / 1e9:.1f} GB free, {what} need about {need_bytes / 1e9:.1f} GB', flush=True)


def profile(plan, name):
    p = dict(PROFILES[name]); p.update((plan.get('profiles') or {}).get(name, {}))
    sw, sh = plan['stage']
    p['scale'] = p['short'] / min(sw, sh)
    p['width'], p['height'] = 2 * round(sw * p['scale'] / 2), 2 * round(sh * p['scale'] / 2)
    p['name'] = name
    return p


def scene_secs(s): return (s['to'] - s['from']) / 1000 / s.get('speed', 1)


def ffmpeg():
    exe = os.environ.get('FFMPEG') or shutil.which('ffmpeg')
    if not exe:
        try: exe = __import__('imageio_ffmpeg').get_ffmpeg_exe()
        except Exception: pass
    if not exe: raise SystemExit('ffmpeg not found: set FFMPEG, put ffmpeg on PATH, or install imageio-ffmpeg (ask the user first)')
    return exe


def chrome():
    exe = os.environ.get('CHROME')
    if exe and os.path.exists(exe): return exe
    cands = []
    if platform.system() == 'Windows':
        for base in (os.environ.get('PROGRAMFILES', r'C:\Program Files'), os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)'), os.environ.get('LOCALAPPDATA', '')):
            cands += [os.path.join(base, 'Google', 'Chrome', 'Application', 'chrome.exe'), os.path.join(base, 'Microsoft', 'Edge', 'Application', 'msedge.exe')]
    elif platform.system() == 'Darwin':
        cands += ['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '/Applications/Chromium.app/Contents/MacOS/Chromium',
                  '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge']
    for name in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'microsoft-edge', 'chrome'):
        w = shutil.which(name)
        if w: cands.append(w)
    for c in cands:
        if c and os.path.exists(c): return c
    raise SystemExit('No Chrome, Chromium or Edge found: set CHROME to its executable')


@functools.lru_cache(maxsize=None)
def font(size, bold=False, italic=False):
    from PIL import ImageFont
    names = {(False, False): ['segoeui.ttf', 'Arial.ttf', 'DejaVuSans.ttf'], (True, False): ['segoeuib.ttf', 'Arial Bold.ttf', 'DejaVuSans-Bold.ttf'],
             (False, True): ['segoeuii.ttf', 'Arial Italic.ttf', 'DejaVuSans-Oblique.ttf'], (True, True): ['segoeuiz.ttf', 'Arial Bold Italic.ttf', 'DejaVuSans-BoldOblique.ttf']}[(bold, italic)]
    dirs = [os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts'), '/System/Library/Fonts/Supplemental', '/Library/Fonts', '/usr/share/fonts/truetype/dejavu', '/usr/share/fonts']
    for n in names:
        for d in dirs:
            for p in glob.glob(os.path.join(d, '**', n), recursive=True)[:1] or [os.path.join(d, n)]:
                if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def font_file(bold=True):
    """a font path for ffmpeg's drawtext, escaped for its filter syntax"""
    f = font(20, bold)
    p = getattr(f, 'path', '') or ''
    return p.replace('\\', '/').replace(':', '\\:')


def run(*a, **k): return subprocess.run([str(x) for x in a], check=True, **k)


def free_port():
    with socket.socket() as s: s.bind(('127.0.0.1', 0)); return s.getsockname()[1]


def up(url):
    try: urllib.request.urlopen(url, timeout=1).read(); return True
    except Exception: return False


def kill(p):
    if p.poll() is not None: return
    if platform.system() == 'Windows':
        subprocess.run(['taskkill', '/PID', str(p.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        p.terminate()
        try: p.wait(5)
        except subprocess.TimeoutExpired: p.kill()


@contextlib.contextmanager
def server(plan):
    """the project's files over http, with the kit under /kit/; a page needs http for its fonts and images"""
    port = free_port()
    p = subprocess.Popen([sys.executable, os.path.join(HERE, 'serve.py'), plan['_root'], str(port), KIT], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(100):
            if up(f'http://127.0.0.1:{port}/kit/kit.js'): break
            time.sleep(0.1)
        else: raise SystemExit('the local server did not start')
        yield f'http://127.0.0.1:{port}'
    finally: kill(p)


@contextlib.contextmanager
def browsers(plan, n):
    """n headless browsers, each on its own port with its own profile, so scenes render side by side"""
    procs, ports = [], []
    base = os.path.join(plan['_root'], '.render', 'chrome')
    try:
        for k in range(max(1, n)):
            port = free_port()
            procs.append(subprocess.Popen([chrome(), '--headless=new', f'--remote-debugging-port={port}', f'--user-data-dir={os.path.join(base, str(k))}',
                                           '--no-first-run', '--no-default-browser-check', '--hide-scrollbars', '--mute-audio', '--lang=en-US',
                                           '--force-color-profile=srgb', 'about:blank'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            for _ in range(150):
                if up(f'http://127.0.0.1:{port}/json/version'): break
                time.sleep(0.1)
            else: raise SystemExit(f'a headless browser did not start. One left from an earlier run (a crash, a killed build) may still '
                                   f'hold its profile: close the browser whose command line names {os.path.join(base, str(k))} and run again')
            ports.append(port)
        yield ports
    finally:
        for port in ports: close_browser(port)
        for p in procs: kill(p)


def close_browser(port):
    """asks the browser on this port to quit: Chrome can relaunch itself (a new profile, an update), and then the process
    that was started is not the browser, so killing it leaves the browser running and holding its profile"""
    try: ws = json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=2))['webSocketDebuggerUrl']
    except Exception: return
    js = ("const w=new WebSocket(process.argv[1]);w.onopen=()=>w.send(JSON.stringify({id:1,method:'Browser.close'}));"
          "w.onmessage=w.onclose=w.onerror=()=>process.exit(0);setTimeout(()=>process.exit(0),3000)")
    try: subprocess.run(['node', '-e', js, ws], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception: pass
    for _ in range(50):
        if not up(f'http://127.0.0.1:{port}/json/version'): return
        time.sleep(0.1)


def default_browsers(jobs):
    return max(1, min(jobs, (os.cpu_count() or 4) // 4))


def page_url(base, page, extra=''):
    sep = '&' if '?' in page else '?'
    return f"{base}/{page.lstrip('/')}" + (sep + extra if extra else '')


def content_key(plan, page, *params):
    """what a scene's frames depend on: its page, the files next to it, the kit and the settings"""
    h = hashlib.sha1(('|'.join(map(str, (page,) + params))).encode())
    root = plan['_root']; path = page.split('?')[0].lstrip('/')
    kit = os.path.join(root, 'kit') if os.path.isdir(os.path.join(root, 'kit')) else KIT
    files = [os.path.join(root, path)]
    for d in {os.path.dirname(os.path.join(root, path)), kit}:
        # the shared files a page may load (recordings included); other pages and the plan itself are not its inputs
        for ext in ('js', 'css', 'png', 'jpg', 'jpeg', 'svg', 'webp', 'woff2', 'json', 'mp4', 'webm', 'mov', 'm4v'):
            files += glob.glob(os.path.join(d, '*.' + ext))
    page_text = open(files[0], encoding='utf-8', errors='replace').read() if os.path.isfile(files[0]) else ''
    media = ('.mp4', '.webm', '.mov', '.m4v')
    for dp, dn, fn in os.walk(root):  # recordings anywhere in the project (not in its renders or results)
        dn[:] = [d for d in dn if d not in ('.render', 'out', 'node_modules') and not d.startswith('.git')]
        files += [os.path.join(dp, f) for f in fn if f.lower().endswith(media)]
    for f in sorted(set(files)):
        # a recording counts only for the pages that name it, so replacing one re-renders only its scenes
        if f.lower().endswith(media) and os.path.basename(f) not in page_text: continue
        if os.path.isfile(f) and os.path.basename(f) != 'plan.json':
            with open(f, 'rb') as fh: h.update(f.encode() + fh.read())
    return h.hexdigest()
