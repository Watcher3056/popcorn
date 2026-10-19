"""A thumbnail or a cover as people will first see it: the full image beside copies shrunk to feed and phone widths,
on one sheet, to check that the subject, the headline and the face still read.
Usage: feedsize.py <image> [--widths 550,320]   writes <image>-feed.png"""
import argparse, os
from PIL import Image, ImageDraw
import common as C

ap = argparse.ArgumentParser(); ap.add_argument('image'); ap.add_argument('--widths', default='550,320'); a = ap.parse_args()
im = Image.open(a.image).convert('RGB'); widths = [int(w) for w in a.widths.split(',')]
big = im.resize((900, round(im.height * 900 / im.width)), Image.LANCZOS)
smalls = [im.resize((w, round(im.height * w / im.width)), Image.LANCZOS) for w in widths]
W = 40 + big.width + sum(s.width + 30 for s in smalls); H = 70 + max([big.height] + [s.height for s in smalls])
sheet = Image.new('RGB', (W, H), (245, 246, 248)); d = ImageDraw.Draw(sheet); f = C.font(18, True)
x = 20; d.text((x, 18), 'full (scaled to 900 px)', font=f, fill=(18, 21, 26)); sheet.paste(big, (x, 50)); x += big.width + 30
for w, s in zip(widths, smalls):
    d.text((x, 18), f'{w} px wide', font=f, fill=(18, 21, 26)); sheet.paste(s, (x, 50)); x += s.width + 30
out = os.path.splitext(a.image)[0] + '-feed.png'; sheet.save(out); print(out)
