from PIL import Image
import os, glob

imgs = sorted(glob.glob('/tmp/kb_results/fixed_*.png'))
print(f"Total images: {len(imgs)}")
for f in imgs:
    try:
        im = Image.open(f)
        print(f"{os.path.basename(f)}: {im.size}, mode={im.mode}")
    except Exception as e:
        print(f"{os.path.basename(f)}: ERROR - {e}")
