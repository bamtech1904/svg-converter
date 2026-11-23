"""PNG / JPEG を vtracer でトレースして SVG 文字列にする。"""

import io
from dataclasses import dataclass

import vtracer
from PIL import Image, ImageOps

SUPPORTED_SUFFIXES = (".png", ".jpg", ".jpeg")

# vtracer は変換中に Python の GIL を離さず画面が止まるため、大きい画像は縮小してから変換する
MAX_SIDE = 2000


@dataclass
class Settings:
    colormode: str = "color"  # "color" | "binary"
    filter_speckle: int = 4  # この面積(px)未満のゴミを消す。大きいほど単純
    color_precision: int = 6  # 色の細かさ(1-8)。小さいほど色数が減る
    mode: str = "spline"  # "spline"(曲線) | "polygon"(直線) | "pixel"


@dataclass
class Result:
    svg: str
    scaled: bool  # MAX_SIDE を超えたため縮小して変換したか
    path_count: int  # 0 なら図形が検出されなかった


def convert(path: str, settings: Settings) -> Result:
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)  # スマホ写真の回転情報を反映
        if img.mode in ("I;16", "I;16B", "I;16L", "I"):
            # 16bit 階調は RGBA 変換で 255 に切り詰められ白飛びするため、8bit に落とす
            img = img.point(lambda v: v / 256).convert("L")
        img = img.convert("RGBA")

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
