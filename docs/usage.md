# Video-presentation usage

The plugin and marketplace are both named `video-presentation`. Only this skill
is included. No other skill or Graph runtime is needed to build or use it.

Remove through `codex plugin remove video-presentation@video-presentation` or
`claude plugin uninstall video-presentation@video-presentation`. It does not
install global Codex role files. Retained client/project data are separate from
plugin removal.

## Requirements and checks

Python 3.11+ and Git. From the repository root:

```sh
python -m pip install -r requirements-dev.txt
python tools/build_plugin.py
python tools/build_plugin.py --host claude
python -m unittest discover -s tests -v
```

Use `py -3` instead of `python` on Windows when needed, or `python3` on
macOS/Linux. Plugin hooks use Python's standard library. Skill builds also need
the pinned PyYAML build dependency. Claude hooks need bash (Git Bash on
Windows).

## Rendering toolkit

The skill's `scripts/` render videos, storyboards, GIFs and stills. They need,
installed separately:

- Node 22 or newer (its built-in WebSocket drives the browser);
- Python 3 with `numpy` and `Pillow`;
- Chrome, Chromium or Edge (`CHROME` points to one the scripts don't find);
- ffmpeg on PATH, in `FFMPEG`, or from the `imageio-ffmpeg` package;
- optionally OpenCV (`opencv-python`) or `qrcode`, to make and check QR codes;
- a text-to-speech engine of your choice for narration.

A project keeps its frames and caches in `.render/` and its results in `out/`.
Nothing is uploaded; the browsers run headless on the local machine.

## Local installation and updates

`python tools/build_plugin.py --install` builds a new version and registers this
repository as the `video-presentation` marketplace. Each build gets a new
version number; rebuild and reinstall to update.
