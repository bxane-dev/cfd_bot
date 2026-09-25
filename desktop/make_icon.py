from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
BUILD.mkdir(exist_ok=True)

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
red = (236, 55, 59, 255)
white = (255, 255, 255, 255)

d.ellipse((118, 118, 906, 906), fill=red)
poly = [
    (166, 350), (318, 350), (384, 482), (451, 350),
    (580, 350), (650, 485), (716, 350), (858, 350),
    (742, 651), (659, 651), (582, 521), (511, 651),
    (386, 651), (315, 519), (250, 651), (166, 651),
    (252, 523)
]
d.polygon(poly, fill=white)
d.polygon([(166, 451), (257, 605), (331, 451), (300, 515), (250, 575)], fill=red)
d.polygon([(520, 451), (590, 579), (653, 451), (620, 524), (579, 601)], fill=red)
d.polygon([(683, 451), (754, 605), (822, 451), (782, 537), (745, 616)], fill=red)

png = BUILD / "icon.png"
ico = BUILD / "icon.ico"
img.save(png)
img.save(ico, sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(f"wrote {png} and {ico}")
