# Popcorn

A reusable skill for presentation media told as a simple story people follow
like a cartoon: a narrated story video (a launch, an explainer, a demo, a
pitch), carousels of slides for a feed, short animated GIF hooks for a README
or a landing page, thumbnails and covers. Its source is in
`skills/popcorn/`. It has its own repository, marketplace, package
and release boundary.

A piece that moves goes through three previews, each approved before the next
(a still or a carousel: the slides at the size people see them, then the file):

1. a storyboard of real frames, rendered from the actual scene pages;
2. a 480p draft with voice and sound, rendered fast;
3. the final render.

Its toolkit renders HTML scene pages frame by frame in headless Chrome, lays
voice, synthesized sound and music under them, and encodes with ffmpeg. A small
sample project is in `skills/popcorn/assets/example/`.

Example in Codex: `$popcorn make a 60-second launch video for this app`.
In Claude Code: `/popcorn:popcorn make a 60-second launch video for this app`.

## Install

```sh
git clone https://github.com/Watcher3056/popcorn.git
cd popcorn
python -m pip install -r requirements-dev.txt
python tools/build_plugin.py --install
```

For Claude Code, use `python tools/build_plugin.py --host claude --install`
instead. Start a new client session after installation.

Rendering needs Node 22+, Python 3 with `numpy` and `Pillow`, Chrome, Chromium
or Edge, and ffmpeg, installed separately.

[Build/install/update/removal and data](docs/usage.md) · [MIT](LICENSE)

Private cases, personal data, research records and agent authoring instructions
are excluded from the public source repository.
