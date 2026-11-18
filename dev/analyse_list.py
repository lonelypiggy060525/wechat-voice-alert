"""Analyse the chat list screenshot: locate red unread badges and row geometry."""
from PIL import Image
import numpy as np

img = Image.open("shot_covered.png").convert("RGB")
a = np.asarray(img).astype(int)
H, W, _ = a.shape
print("size", W, H)

r, g, b = a[:, :, 0], a[:, :, 1], a[:, :, 2]
# WeChat unread badge red ~ (250, 80, 80); muted-dot also red but small
mask = (r > 170) & (g < 110) & (b < 110) & (r - g > 90)
print("red pixels:", int(mask.sum()))

# cluster into blobs by simple flood on rows/cols
ys, xs = np.nonzero(mask)
if len(ys) == 0:
    raise SystemExit("no red pixels")

# group by y gaps
order = np.argsort(ys)
ys_s = ys[order]
xs_s = xs[order]
groups = []
cur = [0]
for i in range(1, len(ys_s)):
    if ys_s[i] - ys_s[i - 1] > 6:
        groups.append(cur)
        cur = []
    cur.append(i)
groups.append(cur)

for grp in groups:
    gy = ys_s[grp]
    gx = xs_s[grp]
    # split each y group by x gaps
    ordx = np.argsort(gx)
    gx_s, gy_s = gx[ordx], gy[ordx]
    start = 0
    for i in range(1, len(gx_s) + 1):
        if i == len(gx_s) or gx_s[i] - gx_s[i - 1] > 8:
            xs_blk = gx_s[start:i]
            ys_blk = gy_s[start:i]
            if len(xs_blk) >= 12:
                print(f"badge x={xs_blk.min()}..{xs_blk.max()} y={ys_blk.min()}..{ys_blk.max()} "
                      f"size={xs_blk.max()-xs_blk.min()+1}x{ys_blk.max()-ys_blk.min()+1} px={len(xs_blk)}")
            start = i

# estimate row pitch from badge y positions
print("\navatar column brightness profile (x=90..125):")
strip = a[:, 90:126, :].mean(axis=(1, 2))
for y in range(80, min(H, 700), 2):
    pass
