"""PNG / JPEG を SVG 文字列にする。

- "color" / "binary": vtracer で輪郭をトレースする（ロゴ・イラスト向け）
- "pixel": 画素をそのまま四角形で書き出す。元画像と画素単位で一致する（ドット絵・アイコン向け）
"""

import io
from collections import defaultdict
from dataclasses import dataclass

import vtracer
from PIL import Image, ImageOps

SUPPORTED_SUFFIXES = (".png", ".jpg", ".jpeg")

# vtracer は変換中に Python の GIL を離さず画面が止まるため、大きい画像は縮小してから変換する
MAX_SIDE = 2000

# ドットモードは縮小しない。代わりに SVG の大きさを決める「四角形の数」で打ち切る。
# 100 万個で SVG は約 20MB。ドット絵や単色の多い画像は大きくても通り、写真やノイズだけが止まる
MAX_RECTS_DOT = 1_000_000
# 読み込み（デコード）だけでメモリを食い尽くさないよう、画素数はヘッダの段階で断る
MAX_PIXELS_DOT = 16_000_000

# Qt の SVG 描画は 1 本のパスで約 32,767 コマンド（四角形約 6,550 個）を超えると途中で打ち切る。
# 余裕を見て 1 本あたりの四角形の数を抑え、超える分は同じ色の別パスに分ける
RECTS_PER_PATH = 4000


@dataclass
class Settings:
    colormode: str = "color"  # "color" | "binary" | "pixel"（画素そのまま）
    filter_speckle: int = 4  # この面積(px)未満のゴミを消す。大きいほど単純
    color_precision: int = 6  # 色の細かさ(1-8)。小さいほど色数が減る
    mode: str = "spline"  # "spline"(曲線) | "polygon"(直線) | "pixel"


@dataclass
class Result:
    svg: str
    scaled: bool  # MAX_SIDE を超えたため縮小して変換したか
    path_count: int  # 0 なら図形が検出されなかった
    # ドットモードのみ: SVG に書き出した画素そのもの（プレビューを SVG と食い違わせないため）
    pixels: Image.Image | None = None


def load_rgba(path: str, max_pixels: int | None = None) -> Image.Image:
    """画像を読み込み、回転情報と色の形式をそろえた RGBA にする。変換とプレビューの両方で使う。"""
    with Image.open(path) as img:
        w, h = img.size  # ヘッダだけで取れる。画素はまだ読み込んでいない
        if max_pixels is not None and w * h > max_pixels:
            raise ValueError(
                f"ドットモードで扱える画像は {max_pixels // 10_000} 万画素までです"
                f"（この画像は {w}×{h} = 約 {w * h // 10_000} 万画素）。"
            )
        img = ImageOps.exif_transpose(img)  # スマホ写真の回転情報を反映（JPEG の EXIF、PNG の eXIf）
        if img.mode in ("I;16", "I;16B", "I;16L", "I"):
            # 16bit 階調は RGBA 変換で 255 に切り詰められ白飛びするため、8bit に落とす
            img = img.point(lambda v: v / 256).convert("L")
        return img.convert("RGBA")


def convert(path: str, settings: Settings) -> Result:
    if settings.colormode == "pixel":
        img = load_rgba(path, max_pixels=MAX_PIXELS_DOT)
    else:
        img = load_rgba(path)

    if settings.colormode == "pixel":
        svg = pixels_to_svg(img)
        return Result(svg=svg, scaled=False, path_count=svg.count("<path"), pixels=img)

    scaled = max(img.size) > MAX_SIDE
    if scaled:
        img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)

    if settings.colormode == "binary":
        # vtracer の白黒モードは明るさで判定しないため（赤が背景扱いで消える）、
        # 透明部分を白で埋めてからグレースケールにして渡す
        bg = Image.new("RGBA", img.size, "white")
        img = Image.alpha_composite(bg, img).convert("L")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    svg = vtracer.convert_raw_image_to_svg(
        buf.getvalue(),
        img_format="png",
        colormode=settings.colormode,
        hierarchical="stacked",
        mode=settings.mode,
        filter_speckle=settings.filter_speckle,
        color_precision=settings.color_precision,
    )
    return Result(svg=svg, scaled=scaled, path_count=svg.count("<path"))


def pixels_to_svg(img: Image.Image) -> str:
    """RGBA 画像の各画素を四角形として書き出す。横に同じ色が続く部分は 1 つにまとめる。"""
    w, h = img.size
    px = img.load()
    runs = defaultdict(list)  # 色 → その色の四角形のパスデータ
    rect_count = 0
    for y in range(h):
        if rect_count > MAX_RECTS_DOT:
            raise ValueError(
                "色の変化が細かすぎて、SVG が大きくなりすぎます（写真などはドットモードに向きません）。"
                "「カラー」か「白黒」で変換してください。"
            )
        x = 0
        while x < w:
            color = px[x, y]
            start = x
            while x < w and px[x, y] == color:
                x += 1
            if color[3] > 0:  # 完全に透明な画素は描かない
                n = x - start
                runs[color].append(f"M{start} {y}h{n}v1h-{n}z")
                rect_count += 1

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        # crispEdges: 拡大表示しても画素の境界をぼかさない
        f'viewBox="0 0 {w} {h}" shape-rendering="crispEdges">\n'
    ]
    for (r, g, b, a), paths in runs.items():
        opacity = f' fill-opacity="{a / 255:.4f}"' if a < 255 else ""
        for i in range(0, len(paths), RECTS_PER_PATH):
            d = "".join(paths[i : i + RECTS_PER_PATH])
            parts.append(f'<path fill="#{r:02x}{g:02x}{b:02x}"{opacity} d="{d}"/>\n')
    parts.append("</svg>\n")
    return "".join(parts)
