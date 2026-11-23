"""配布 zip に同梱するライセンス文書を 1 つのフォルダに集める。

使い方: python scripts/collect_licenses.py <出力フォルダ>
ライブラリのライセンス本文は、ビルドに使ったインストール済みパッケージから原文をコピーする。
"""

import shutil
import sys
from importlib.metadata import distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# パッケージ名 → 同梱するライセンスファイル（dist-info 内の相対パス）
PACKAGE_LICENSES = {
    "vtracer": "licenses/LICENSE",
    "Pillow": "licenses/LICENSE",
    "pyinstaller": "licenses/COPYING.txt",
}


def main(out: Path):
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "LICENSE", out / "SvgConverter-LICENSE.txt")
    shutil.copy(ROOT / "THIRD_PARTY_NOTICES.md", out / "THIRD_PARTY_NOTICES.md")
    for f in (ROOT / "licenses").iterdir():
        shutil.copy(f, out / f.name)

    for name, rel in PACKAGE_LICENSES.items():
        dist = distribution(name)
        matches = [f for f in dist.files or [] if f.as_posix().endswith(f".dist-info/{rel}")]
        if not matches:
            sys.exit(f"license file not found for {name}: {rel}")
        shutil.copy(dist.locate_file(matches[0]), out / f"{name}-LICENSE.txt")

    py_license = Path(sys.base_prefix) / "LICENSE.txt"  # Windows
    if not py_license.is_file():
        py_license = Path(sys.base_prefix) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "LICENSE.txt"
    if not py_license.is_file():
        sys.exit(f"Python license file not found under {sys.base_prefix}")
    shutil.copy(py_license, out / "Python-LICENSE.txt")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
