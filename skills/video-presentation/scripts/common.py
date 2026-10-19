"""Shared helpers for the toolkit: finding Chrome, ffmpeg and fonts, the local server and a pool of headless browsers.
Every tool takes the project's plan.json; the project folder holds the scene pages, and the kit is served under /kit/."""
import contextlib, glob, hashlib, json, os, platform, shutil, socket, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = HERE  # kit.js and kit.css live next to the scripts; a project may override them with its own kit/ folder

PROFILES = {
    # the storyboard's still frames: the stage at its own size, crisp enough to judge the look
    'board': dict(fps=0, height=720, format='png'),
    # the 480p check of rhythm, timing and sound: fewer frames, JPEG frames, the fastest encoder there is
    'draft': dict(fps=24, height=480, format='jpeg', encoder='fast'),
    # the approved cut in full quality
    'final': dict(fps=30, height=1080, format='png', encoder='quality'),
    # frames for an animated GIF (gif.py stitches them)
    'gif': dict(fps=20, height=540, format='png'),
}


def load_plan(path):
    with open(path, encoding='utf-8') as f: plan = json.load(f)
    plan['_root'] = os.path.dirname(os.path.abspath(path))
    plan.setdefault('name', os.path.basename(plan['_root']))
    plan.setdefault('stage', [960, 540])
    plan.setdefault('scheme', 'light')
    plan.setdefault('background', '#f5f6f8')
    ids = [s['id'] for s in plan['scenes']]
    if len(set(ids)) != len(ids): raise SystemExit('plan.json: scene ids repeat')
    return plan


def profile(plan, name):
    p = dict(PROFILES[name]); p.update((plan.get('profiles') or {}).get(name, {}))
    p['scale'] = p['height'] / plan['stage'][1]
    p['width'] = 2 * round(plan['stage'][0] * p['scale'] / 2)
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
            else: raise SystemExit('a headless browser did not start')
            ports.append(port)
        yield ports
    finally:
        for p in procs: kill(p)


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
        # the shared files a page may load; other pages and the plan itself are not its inputs
        for ext in ('js', 'css', 'png', 'jpg', 'jpeg', 'svg', 'webp', 'woff2', 'json'):
            files += glob.glob(os.path.join(d, '*.' + ext))
    for f in sorted(set(files)):
        if os.path.isfile(f) and os.path.basename(f) != 'plan.json':
            with open(f, 'rb') as fh: h.update(f.encode() + fh.read())
    return h.hexdigest()
