# Toolkit

The scripts in `scripts/` turn a folder of scene pages and one `plan.json` into a storyboard, a draft, a final video, GIFs, carousels and stills. Every frame is rendered from the real pages, with any real recording playing inside them, so each preview shows the piece's real look ([VID-REAL-FRAMES]). `assets/example/` is a small working project to copy from.

**Needs:**
- Node 22 or newer (its built-in WebSocket drives the browser);
- Python 3 with `numpy` and `Pillow`;
- Chrome, Chromium or Edge (`CHROME` points to one the scripts don't find);
- ffmpeg, on PATH, in `FFMPEG`, or from the `imageio-ffmpeg` package;
- optionally, for QR codes, OpenCV (`opencv-python`), which also decodes each code back to check it; `qrcode` alone writes the code unchecked.

Missing pieces are installed only with the user's yes ([VID-ASK-INSTALL]); when the user declines, the script table is the preview ([VID-REAL-FRAMES]). On Windows, run Python with `PYTHONUTF8=1`.

## A project

```
my-video/
  plan.json         the scenes, their order and timing, the voice lines, the music
  scenes/*.html     one page per scene (plus its own .css / .js / images / recordings)
  voice/<id>.wav    the narration, one file per line (voice_prep.py makes them)
  out/              what the user gets: storyboards, videos, GIFs, carousels, sheets, timelines; earlier versions in out/old/
  .render/          frames and caches; reused by the next build
```

- **Where it lives:** outside the product's own source tree, or in a git-ignored folder. `.render/` holds many frames.
- **How it's served:** the pages go over local http with the kit under `/kit/`; a project with its own `kit/` folder overrides the kit file by file.

## A scene page

The page's stage is the plan's `stage` size, wide, vertical or square. A page builds its whole timeline when it loads and draws any moment on request: `seek(t)` sets every element for page time `t` (ms). Nothing reads the clock, so any frame at any rate comes out the same every time.

```html
<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="/kit/kit.css"><link rel="stylesheet" href="my.css"></head>
<body><div id="stage"></div>
<script src="/kit/kit.js"></script>
<script>
const head = el('div', 'my-h abs', null, 'Three steps to a clean inbox'); box(head, 120, 90, 720);
show(head, 200);                                   // fades and rises in at 200 ms
const card = el('div', 'card abs', null, '…'); box(card, 120, 220, 360);
pop(card, 900);                                    // pops in with a 'pop' cue
xmark(500, 230, 2200);                             // a red ✕ with a 'fail' cue
window.TOTAL = 4000;                               // the page's length in ms
finalize();
</script></body></html>
```

Give a scene's own pieces their own class names (a prefix such as `my-`), so no kit class reaches them.

**Kit, the main helpers** (`scripts/kit.js`; read it for the rest):

| Helper | What it does |
| --- | --- |
| `pt(node, prop, t, v, ease)` | A point of a track. Props: `o` opacity, `x` `y` px, `s` scale, `sx` horizontal scale, `r` rotation, `cw` / `ch` visible width / height in %. Ease: `io` (default), `out`, `in`, `lin`, `step`. |
| `el`, `box`, `esc` | Make an element, place it, escape text (a `<` in a label is read as a tag otherwise). |
| `show`, `hide`, `pop`, `slide`, `swap` | Common moves; `swap(old, new, t)` takes the old text away before the new one comes. |
| `title`, `chip` | A title card over the scene (its own background), a caption chip. |
| `cursor(stops, clicks, t0, t1)` | A pointer moving through stops, with click ripples and click cues. |
| `xmark`, `okmark`, `ring` | A red ✕, a green ✓, a light outline on a thing. |
| `typeText`, `counter`, `textBlock`, `stream` | Text typed in with ticks, a number that runs, abstract text as bars, bars that stream in and scroll. |
| `world`, `cam` | A layer the camera pans and zooms over. |
| `compare(...)` | Before → after in one frame, wiped with a handle. |
| `video(src, x, y, w, h, t0, rate)` | A real recording in the scene: it shows its moment `(t − t0) × rate`, frame-exact, muted. |
| `every(fn)` | Anything that isn't a number (text, a class) set per frame. |
| `sfx(t, kind)` | A sound cue at page time `t`; the kinds are in `scripts/sound.py`. |

A story label in the corner comes from the plan (`"tag"`, `"tone": "bad" | "good"`) and fades in after the transition into the scene (`"tagin": 0` keeps it from the first frame).

## Real footage

The toolkit doesn't capture a screen or a camera. A recording comes from whatever records the product: the system's screen recorder, a scripted browser, the product's own capture, a camera, etc. Put the file inside the project (H.264 MP4 or WebM plays in the browser), then:

- **A real presentation:** a scene with `video(...)` filling the stage; labels at the edge ([CR-MARK]) or a cursor where they help; the storyboard's frames are its own stills.
- **A voice-over for an existing video:** a plan with `"over": {"file": "footage.mp4", "gain": 1}` and `"scenes": []`; each voice line's `at` is seconds from the video's start.
  - The draft is a small copy; the final keeps the video's own picture as it is (no re-render, its own frame rate and quality).
  - The video's own sound steps back under the voice; `gain` 1 keeps it at its level.
  - When the footage needs burned subtitles, labels, cuts or a frame around it, use scenes with `video(...)` instead. For a hook picture as its frame 0 ([CR-FEED]), start the footage on its hook moment, or use such scenes.
- **A video from an existing deck:** export its slides as images (the presentation app's own export; an install needs the user's yes) and place each as a scene's picture.
- **Several takes:** one scene per take, each with its range.

## A carousel

A plan whose `stage` is the slide's shape, as the platform asks (e.g. `[540, 675]` gives 1080×1350, a 4:5 portrait; another feed may want a square or 9:16), one scene per slide in order. Each slide is its page as it stands at the scene's last `board` time (else its `to`), so a page can animate in and still give a finished slide. A slide made from a video's scene reuses that page, its corner label included, with a range of its own. The phone sheet shows the slides at the width a phone gives them: check every word that matters there ([CR-CAROUSEL]).

## plan.json

```json
{
  "name": "launch",
  "stage": [960, 540],
  "scheme": "light",
  "background": "#f5f6f8",
  "transition": {"kind": "swipe", "secs": 0.3},
  "scenes": [
    {"id": "intro", "name": "Who and why", "page": "scenes/intro.html", "from": 0, "to": 5200, "speed": 1,
     "transition": "fade", "tag": "1 · Lost receipts", "tone": "bad",
     "status": "new", "board": [800, 3600], "screen": "What happens on screen, for the storyboard."}
  ],
  "voice": {"dir": "voice", "lines": [{"id": "1", "scene": "intro", "at": 0.3, "text": "The line as spoken."}]},
  "music": [{"scene": "intro", "at": 0, "mood": "light"}]
}
```

- `stage`: the page's size in CSS pixels and so its shape. A vertical piece uses e.g. `[540, 960]`. The profiles size the short side, so the final of a vertical stage is 1080×1920.
- A scene plays its page from `from` to `to` (ms) at `speed`; one page can serve several scenes with different ranges.
- `transition`, per scene (into the next) or the plan's default: `swipe`, `fade` or `cut`. The next scene's first frames overlap this one's last ones for `secs`. `cut` is instant: use it only where a hard jump is the point ([CR-TRANSITIONS]). `"sound": "swipe"` (or another cue kind) puts a cue under every transition; there is none by default ([SV-FX]).
- `board`: the page times the storyboard shows for the scene, its beats left to right. `status`: `new`, `changed` or `kept`.
- Voice `at`: seconds from the scene's start in the finished video (the start of the transition into it).
- `music`: moods `light`, `warm`, `tense` or `silent`, each from a point on. Or `{"file": "music/track.mp3", "gain": 0.35}` for a track the user chose (0.35 is the default; 1 keeps a recording's own sound at its level).
- `loudness`: the platform's target in LUFS (default −16, common for web video). `max_mb`: the platform's file-size cap, if it has one.
- `cover`: `{"page": "scenes/cover.html", "t": 0}` or `{"image": "art/cover.png"}`, the hook picture complete ([CR-FEED]), cropped to the frame's shape (the build warns when it had to crop). It becomes frame 0, the file's embedded cover, `…-cover.jpg` for the platform's custom thumbnail, and the storyboard's first row.
  - It replaces frame 0 only: on play it shows for one frame, then the first scene runs. Open that scene on the same picture where the flash would jar.
  - A voice-over (`over`) gets it embedded and as the JPG; its frame 0 stays the video's own. A GIF has none: its first frame is part of the loop.
  - Without one, the build warns when frame 0 is nearly empty.
- `captions`: the subtitles. A `.srt` is written from the voice lines whenever they have text; a line's `"caption"` is shown instead of its `"text"` where the text is spelled for the engine ([SV-WRITE]).
  - `{"burn": true}` also draws them into the picture, one at a time, wrapped and sized to the frame's width, in a strip of their own: `"strip": 0.14` of the height, `"place": "bottom"` or `"top"`, `"words": 7` a subtitle. The scene shrinks to make room, with margins at its sides; the cover frame stays whole.
  - A voice-over gets the `.srt` only, since its picture stays as it is.
- `variants`: other versions of the same piece, e.g. `{"short": {"drop": ["intro"], "drop_lines": ["7"], "lines": {"3": {"file": "3-b", "text": "…"}}, "scenes": {"outro": {"page": "scenes/outro-plain.html"}}}}`.
  - What a variant can do: leave scenes and lines out, swap a line for another take and its text, and change a scene that differs inside (its fields replaced: another page, another range, etc.). Any other key, or an id the plan lacks, stops the build.
  - `--variant short` builds it as `out/<name>-short-…`; the scenes it shares come from the cache, and a scene it changes renders into a cache of its own, so switching between versions renders nothing again.
  - A voice line's `"file"` names its take (default: its id). `voice_prep.py` writes every file the plan and its variants name; `raw/3-b.wav` and `raw/3-b-<take>.wav` are takes of `3-b`, not of `3`.
- `profiles`: overrides per profile, e.g. `{"draft": {"fps": 20}}`, `{"final": {"crf": 20}}`, `{"gif": {"short": 400, "colors": 128, "max_mb": 5}}`.

## Commands, by stage

All run from anywhere; paths are the project's. `S` is this skill's `scripts/` folder.

| Stage | Command | Writes |
| --- | --- | --- |
| [VID-BOARD] | `python S/storyboard.py plan.json [--only changed,new]` | `out/<name>-storyboard-<n>.png` |
| [VID-BOARD] the cover | `python S/still.py plan.json scenes/cover.html <t> out/cover.png`, then `python S/feedsize.py out/cover.png` (an image cover: `feedsize.py` on the image) | the cover and its feed-size sheet, to approve with the storyboard |
| [VID-SOUND] voice | the engine writes `raw/<id>.wav` (or `<id>-<take>.wav` takes), then `python S/voice_prep.py plan.json raw` | `voice/<id>.wav`, a pace table |
| [VID-SOUND] effects | `python S/sound_sample.py plan.json --profile draft --ranges 12-17,40-44 --try "A · soft tone" swipe=glide` | `out/<name>-sound-sample.mp4` |
| [VID-DRAFT] video | `python S/build.py plan.json --draft` | `out/<name>-draft-480p.mp4`, `…-transitions.png`, `…-timeline.json` |
| [VID-FINAL] video | `python S/build.py plan.json --final` | `out/<name>-final-1080p.mp4` and its sheet and timeline |
| [VID-DRAFT] / [VID-FINAL] loop | `python S/build.py plan.json --profile gif-draft`, then `--profile gif` | `out/<name>-gif-draft-300p.gif`, then `…-gif-540p.gif`, each with its sheet and timeline |
| A voice-over (a plan with `over`) | `python S/build.py over.json --draft`, then `--final` | `out/<name>-draft-480p.mp4`, then `out/<name>-final-original.mp4` |
| A carousel ([CR-CAROUSEL]) | `python S/carousel.py plan.json` | `out/<name>-carousel.pdf`, each slide as a PNG, `…-carousel-sheet.png` (all slides) and `…-carousel-phone.png` (at a phone's width) |
| A still, a thumbnail | `python S/still.py plan.json scenes/thumb.html 0 out/thumb.png --css 1280x720 --px 1920x1080`, then `python S/feedsize.py out/thumb.png` | the image and a feed-size sheet |
| A QR code | `python S/qr.py <url> out/qr.png` | the code, decoded back to check it |

`build.py`, `storyboard.py`, `sound_sample.py` and `carousel.py` take `--variant <name>`. Run long builds in the background and read their summary when they finish. One build runs at a time per project (a second one stops at once), so versions build one after another. `gif.py` also makes a GIF from frame folders by hand.

## What the build checks and prints

- **Scene timing:** each scene's start time and length in the finished video. A timestamp the user flags maps to its scene here, and `…-timeline.json` lists every scene, voice line and sound cue by time ([VID-ROUND]).
- **Warnings:**
  - voice lines that overlap, follow each other with no breath, or run past their scene;
  - voice files missing;
  - a file over its cap;
  - frame 0 nearly empty, with no `cover` ([CR-FEED]);
  - the disk nearly full. Before rendering, the build estimates the frames' size (the subtitled copy of every frame included) and stops when the disk can't hold them; it deletes nothing to make room (old frames in `.render/` can be rebuilt; the user decides);
  - a cover cropped to the frame's shape;
  - burned subtitles: a reminder to turn the platform's automatic subtitles off.
- **Loudness** as measured, against the target.
- **`…-transitions.png`:** frames just before, during and just after every transition, plus the loop's seam for a GIF, for the leaks and jumps the eye has to judge ([CR-TRANSITIONS]).
- **Versions:** where the earlier version went. A build, a storyboard, a sound sample and a carousel each move their earlier files to `out/old/<time>/`.
- **Also written:** the `.srt`, and with a cover the `…-cover.jpg`; the summary lists them.

## Speed

What makes the previews cheap, and is already in the build:

- **The draft** renders at 480p with fewer frames a second and JPEG frames. It encodes with the GPU encoder when there is one, else with a fast CPU preset. A loop's draft is the GIF itself, small.
- **Parallel browsers:** scenes render side by side in several headless browsers, the longest first.
- **The cache:** a scene renders again only when its page, the files next to it (a recording, wherever it sits in the project, counts for the pages that name it), the kit or its settings changed, so a change to one scene re-renders that scene. `--force` renders everything.
- **Scenes render without the voice;** the voice lines' lengths then decide where each sits and whether a scene runs long enough (the warnings say). Don't render while a GPU voice model is running ([SV-TAKES]).

The build warns when capture crawls (seconds a frame): look for another job holding the GPU or the CPU before changing the scenes or the scripts.

## When something goes wrong

| What you see | Usual cause |
| --- | --- |
| "another build of this project is running" | A build, a storyboard, a carousel, a sound sample or a still is still running in this project: let it finish. |
| "a headless browser did not start" | A browser left from an earlier run (a crash, a killed build) still holds the profile the message names: close that browser and run again. |
| "the page did not get ready" | The page threw before `finalize()` (open it in a browser and read its console), never set `window.TOTAL`, or a recording in it can't load. |
| `WebSocket is not defined`, or `node` not found | Node is missing or older than 22. |
| A scene looks unstyled, or its layout is odd | A scene class with the same name as a kit class (see A scene page). |
| An element is visible before its time | Two points at the same time on one track, or a show without a hide; the track holds its first value before its first point. |
| An icon or label comes out empty | Text with `<` set as HTML: use `esc()`. |
| A recording stays black or frozen | The file is outside the project, or its codec doesn't play in the browser: convert it to H.264 MP4. |
| A box instead of ✓ ✕ → in an image made with Python | The font has no such glyph: draw the shape, or use words. |
| A scrolling panel doesn't scroll | A flex or grid child needs `min-height: 0`. |
| Frames of the previous beat show at a scene's start | The scene's `from` starts while the page's earlier beat is still leaving: start it later. |
| The browsers or the server are gone after a restart | The build starts its own each time; just run it again. |
