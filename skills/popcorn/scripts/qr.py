"""A QR code for a link on an end card, checked by decoding it back: a code that doesn't decode to the exact link
is worse than none. Usage: qr.py <url> <out.png> [--size 600]
Uses OpenCV (cv2) when it is installed, else the qrcode package; with neither, it says what is missing."""
import argparse, sys

ap = argparse.ArgumentParser(); ap.add_argument('url'); ap.add_argument('out'); ap.add_argument('--size', type=int, default=600); a = ap.parse_args()
try:
    import cv2, numpy as np
except ImportError:
    cv2 = None
img = None
if cv2 is not None and hasattr(cv2, 'QRCodeEncoder'):
    q = cv2.QRCodeEncoder.create().encode(a.url)
    img = cv2.resize(q, (a.size, a.size), interpolation=cv2.INTER_NEAREST)
    img = cv2.copyMakeBorder(img, 24, 24, 24, 24, cv2.BORDER_CONSTANT, value=255)
    cv2.imwrite(a.out, img)
else:
    try:
        import qrcode
    except ImportError:
        sys.exit('needs opencv-python or qrcode: ask the user before installing either')
    qrcode.make(a.url).resize((a.size, a.size)).save(a.out)
if cv2 is not None:
    got, _, _ = cv2.QRCodeDetector().detectAndDecode(cv2.imread(a.out))
    if got != a.url: sys.exit(f'{a.out}: decodes to {got!r}, not {a.url!r}')
    print(a.out, 'decodes back to', got)
else:
    print(a.out, 'written; not checked (no OpenCV to decode it)')
