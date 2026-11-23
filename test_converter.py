from PIL import Image, ImageDraw

from converter import MAX_SIDE, Settings, convert


def _sample(path, fmt, size=(120, 120), **save_kwargs):
    img = Image.new("RGB", size, "white")
    w, h = size
    ImageDraw.Draw(img).ellipse((w // 6, h // 6, w * 5 // 6, h * 5 // 6), fill="red")
    img.save(path, fmt, **save_kwargs)


def test_png_color(tmp_path):
    p = tmp_path / "a.png"
    _sample(p, "PNG")
    r = convert(str(p), Settings())
    assert r.svg.lstrip().startswith("<?xml")
    assert 'width="120"' in r.svg
    assert "#FF0000" in r.svg.upper() or "#FE0000" in r.svg.upper()
    assert not r.scaled


def test_jpeg_binary_detects_red_shape(tmp_path):
    p = tmp_path / "a.jpg"
    _sample(p, "JPEG")
    assert convert(str(p), Settings(colormode="binary")).path_count > 0


def test_exif_rotation_applied(tmp_path):
    p = tmp_path / "rot.jpg"
    exif = Image.Exif()
    exif[0x0112] = 6  # Orientation: 90° 回転して表示
    _sample(p, "JPEG", size=(200, 100), exif=exif)
    svg = convert(str(p), Settings()).svg
    assert 'width="100"' in svg and 'height="200"' in svg


def test_large_image_is_scaled(tmp_path):
    p = tmp_path / "big.png"
    _sample(p, "PNG", size=(MAX_SIDE * 2, 100))
    r = convert(str(p), Settings())
    assert r.scaled
    assert f'width="{MAX_SIDE}"' in r.svg


def test_16bit_grayscale_not_blown_out(tmp_path):
    p = tmp_path / "g16.png"
    Image.new("I;16", (60, 60), 16448).save(p)  # 約 25% の明るさ
    r = convert(str(p), Settings(colormode="binary"))
    assert r.path_count > 0  # 白飛びしていれば図形が出ない
