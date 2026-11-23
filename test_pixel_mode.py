import random
import re

import pytest
from PIL import Image

from converter import MAX_PIXELS_DOT, MAX_RECTS_DOT, MAX_SIDE, RECTS_PER_PATH, Settings, convert

PATH_RE = re.compile(r'<path fill="#(\w{6})"(?: fill-opacity="([\d.]+)")? d="([^"]*)"/>')
RECT_RE = re.compile(r"M(\d+) (\d+)h(\d+)v1h-\d+z")


def rebuild(svg: str) -> Image.Image:
    """SVG の四角形を塗り直して画像に戻す（変換が画素を正しく書き出したかの検証用）。"""
    w = int(re.search(r'width="(\d+)"', svg).group(1))
    h = int(re.search(r'height="(\d+)"', svg).group(1))
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for color, opacity, d in PATH_RE.findall(svg):
        rgb = tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))
        a = round(float(opacity) * 255) if opacity else 255
        for x, y, n in RECT_RE.findall(d):
            for dx in range(int(n)):
                assert img.getpixel((int(x) + dx, int(y)))[3] == 0, "四角形が重なっている"
                img.putpixel((int(x) + dx, int(y)), (*rgb, a))
    return img


def test_pixel_mode_reproduces_every_pixel(tmp_path):
    random.seed(0)
    palette = [(255, 255, 255, 255), (0, 0, 0, 255), (230, 57, 70, 255), (10, 20, 30, 128), (0, 0, 0, 0)]
    img = Image.new("RGBA", (40, 30))
    for y in range(30):
        for x in range(40):
            img.putpixel((x, y), random.choice(palette))
    p = tmp_path / "dot.png"
    img.save(p)

    rebuilt = rebuild(convert(str(p), Settings(colormode="pixel")).svg)
    for y in range(30):
        for x in range(40):
            o = img.getpixel((x, y))
            if o[3] == 0:
                assert rebuilt.getpixel((x, y))[3] == 0
            else:
                assert rebuilt.getpixel((x, y)) == o


def test_pixel_mode_splits_long_paths(tmp_path):
    # 1 列おきに黒い画素 → 黒の四角形が RECTS_PER_PATH を大きく超える
    img = Image.new("RGB", (200, 100), "white")
    for y in range(100):
        for x in range(0, 200, 2):
            img.putpixel((x, y), (0, 0, 0))
    p = tmp_path / "stripes.png"
    img.save(p)
    svg = convert(str(p), Settings(colormode="pixel")).svg
    counts = [len(RECT_RE.findall(d)) for _, _, d in PATH_RE.findall(svg)]
    assert max(counts) <= RECTS_PER_PATH
    assert sum(counts) == 200 * 100  # 黒 100 列 × 100 行 + 白 100 列 × 100 行
    assert rebuild(svg).convert("RGB").tobytes() == img.tobytes()


def test_pixel_mode_does_not_scale(tmp_path):
    p = tmp_path / "wide.png"
    Image.new("RGB", (MAX_SIDE + 500, 10), "red").save(p)
    r = convert(str(p), Settings(colormode="pixel"))
    assert not r.scaled
    assert f'width="{MAX_SIDE + 500}"' in r.svg


def test_pixel_mode_rejects_huge_image(tmp_path):
    p = tmp_path / "huge.png"
    Image.new("RGB", (MAX_PIXELS_DOT // 1000 + 1, 1000), "red").save(p)
    with pytest.raises(ValueError, match="万画素"):
        convert(str(p), Settings(colormode="pixel"))


def test_pixel_mode_rejects_too_many_rects(tmp_path):
    # 写真やノイズのように隣り合う色が全部違う画像は、四角形が多すぎるので断る
    random.seed(0)
    side = int(MAX_RECTS_DOT**0.5) + 20
    img = Image.frombytes("RGB", (side, side), random.randbytes(side * side * 3))
    p = tmp_path / "noise.png"
    img.save(p)
    with pytest.raises(ValueError, match="色の変化が細かすぎ"):
        convert(str(p), Settings(colormode="pixel"))


@pytest.mark.parametrize("fmt", ["JPEG", "PNG"])
def test_pixel_mode_applies_exif_rotation(tmp_path, fmt):
    exif = Image.Exif()
    exif[0x0112] = 6  # 90° 回転して表示
    p = tmp_path / f"rot.{fmt.lower()}"
    Image.new("RGB", (50, 30), "red").save(p, fmt, exif=exif)
    r = convert(str(p), Settings(colormode="pixel"))
    assert 'width="30"' in r.svg and 'height="50"' in r.svg
    assert r.pixels.size == (30, 50)  # プレビューに使う画素も回転後


def test_pixel_mode_palette_with_transparency(tmp_path):
    img = Image.new("P", (8, 4))
    img.putpalette([255, 0, 0, 0, 255, 0, 0, 0, 255] + [0] * (256 * 3 - 9))
    for y in range(4):
        for x in range(8):
            img.putpixel((x, y), (x + y) % 3)
    img.info["transparency"] = bytes([255, 128, 0])  # 赤=不透明, 緑=半透明, 青=透明
    p = tmp_path / "pal.png"
    img.save(p, transparency=bytes([255, 128, 0]))

    expected = Image.open(p).convert("RGBA")
    rebuilt = rebuild(convert(str(p), Settings(colormode="pixel")).svg)
    for y in range(4):
        for x in range(8):
            o = expected.getpixel((x, y))
            assert rebuilt.getpixel((x, y)) == (o if o[3] else (0, 0, 0, 0))
