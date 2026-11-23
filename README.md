# SVG Converter

PNG / JPEG 画像をトレースして SVG に変換するデスクトップアプリ（Windows / macOS）。
ロゴ・アイコン・イラストのように色数が少なく輪郭がはっきりした画像向け。写真はポスター風になる。
長辺が 2000px を超える画像は、変換中に画面が固まらないよう 2000px に縮小してから変換する。

## 動作環境

- macOS 14.4 以上、Apple Silicon（M1 以降）のみ。Intel Mac では動かない
- Windows 10 / 11（64bit）

## ダウンロード

[Releases](https://github.com/bamtech1904/svg-converter/releases/latest) から使う OS の zip をダウンロードして展開する。

- Windows: `SvgConverter-windows.zip`
- macOS: `SvgConverter-macos.zip`

## 初回起動（署名なしのため警告が出る）

- **macOS**: zip を展開して `SvgConverter.app` を開くと「開けません」と出る。システム設定 → プライバシーとセキュリティ →「このまま開く」を押す。
  または次のコマンドで隔離属性を外す: `xattr -dr com.apple.quarantine SvgConverter.app`
- **Windows**: `SvgConverter\SvgConverter.exe` を開くと SmartScreen の警告が出る。「詳細情報」→「実行」を押す。
- （開発者向け）GitHub Actions の Artifact からダウンロードした場合は、zip がさらに zip で包まれている。1 回展開すると中にもう 1 つ zip があるので、それも展開する。

## 開発（Mac）

```bash
uv venv -p 3.12
uv pip install -r requirements-dev.txt
.venv/bin/python app.py          # 起動
.venv/bin/python -m pytest -q    # テスト
```

## ビルド

配布用ビルドは GitHub Actions（`.github/workflows/build.yml`）で Windows と macOS の両方を作る。
main への push で実行され、Actions の実行結果ページの Artifacts から zip をダウンロードできる（保持 14 日）。

リリースするときは、バージョンのタグを push する。ビルドが両 OS で成功すると、GitHub Release が作られて zip が添付される。

```bash
git tag v0.2.0
git push origin v0.2.0
```

手元で .app を作って確かめる場合:

```bash
.venv/bin/pyinstaller --noconfirm --windowed --name SvgConverter app.py
open dist/SvgConverter.app
```

## 構成

- `converter.py` — 変換処理（vtracer）。画面に依存しない
- `app.py` — 画面（PySide6）
- `test_converter.py` — 変換処理のテスト
- `scripts/collect_licenses.py` — 配布 zip に同梱するライセンス文書を集める（Actions から実行）

## ライセンス

MIT License（`LICENSE`）。配布するアプリには Qt / PySide6（LGPL-3.0）、vtracer、Pillow などを同梱している。
一覧は `THIRD_PARTY_NOTICES.md`、各ライセンスの本文は配布 zip の `licenses/` フォルダにある。
