# STATE.md — svg-converter

> セッション開始時に読み、終了時に更新する。運用ルールは `~/.claude/CLAUDE.md` の「状態ファイル（STATE.md）運用」を参照。
> このファイルはリポジトリにコミットする。

## 検証済み事実

- vtracer 0.6.15（PyPI 最新リリース）の Python API は `convert_raw_image_to_svg(bytes, img_format, colormode=..., ...)`。Context7 / GitHub master の `Config` / `clustering` は未リリースの新 API で、0.6.15 で `clustering=` を渡すと TypeError。インストール版で直接呼んで確認（2026-11-23）
- vtracer 0.6.15 は Windows（win_amd64 / win_arm64）と macOS（arm64 / x86_64）の cp312 wheel を提供している。PyPI JSON API で確認（2026-11-23）
- vtracer の `colormode="binary"` は明るさで判定しない。白地に赤い円の RGB 画像では path が 0 本、グレースケール（L）に変換すると 1 本出る。`converter.py` で白黒時は白背景合成→L 変換して回避。スクリプトで比較して確認（2026-11-23）
- Mac（arm64, macOS 26.6）で PyInstaller の `--windowed` ビルドが成功し、.app は約 110MB、起動して 5 秒以上落ちずに動作（2026-11-23）
- GUI はオフスクリーン描画で JPEG 読み込み→変換→保存ボタン有効化まで動作（2026-11-23）
- vtracer は変換中に GIL を解放しない。別スレッドでも UI が止まる（qa-reviewer が 4000x3000 ノイズ画像で 51 秒 GIL 保持を実測）。対策として長辺 2000px 超は縮小して変換（2026-11-23）
- Qt の `QPixmap(path)` は EXIF 回転を反映しない。`QImageReader.setAutoTransform(True)` で反映され、変換結果と向きが一致。オフスクリーンで確認（2026-11-23）
- PySide6 メタパッケージを `PySide6-Essentials` に替えても QtSvg を含めて動作し、.app は 110MB → 90MB（2026-11-23）
- GitHub Actions（bamtech1904/svg-converter, run 45192099367）で Windows / macOS とも成功。Mac 版 Artifact を展開した arm64 .app は 5 秒以上起動を維持（2026-11-23）
- リポジトリは公開（2026-11-23）。MIT ライセンス。配布 zip の licenses/ に LGPL/GPL 本文と各ライブラリのライセンス原文が入ることを run 45194378450 の Artifact で確認。PySide6 の wheel にはライセンス本文が無いため LGPL/GPL は gnu.org から取得してリポジトリに置いている（2026-11-23）
- ビルドした .app の Qt は最小 macOS 14.4、arm64 のみ（qa-reviewer が vtool で確認、2026-11-23）

## 一般則

-

## 未解決の失敗

- Windows 版の実機動作が未確認（Actions でのビルド成功と、zip に SvgConverter.exe・vtracer の pyd・qsvg.dll が入っていることまでは確認済み）

## 教訓

-

## 前回セッション

- 2026-11-23 · MVP（変換・プレビュー・保存・Actions 設定）を作成しローカル検証済み。qa-reviewer の重大指摘 0、中・軽微指摘は対応済み。非公開リポジトリ bamtech1904/svg-converter に push し Actions は両 OS 成功。次: Windows（仮想マシン）で exe を起動し PNG/JPEG の変換と保存を確認
