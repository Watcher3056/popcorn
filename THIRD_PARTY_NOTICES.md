# External dependencies

Build-time metadata validation uses separately installed PyYAML (MIT), pinned in requirements-dev.txt: https://github.com/yaml/pyyaml/blob/main/LICENSE . The plugin hooks use Python's standard library.

The rendering toolkit calls separately installed programs and packages, none of which is copied into the package: Node.js, a Chromium-based browser, ffmpeg (or the imageio-ffmpeg package), numpy, Pillow, and optionally OpenCV or qrcode. Voices made with a text-to-speech engine carry that engine's own terms. Agent hosts are separately installed products with their own terms.

The repository's own material is covered by [LICENSE](LICENSE). See [asset provenance](docs/asset-provenance.md).
