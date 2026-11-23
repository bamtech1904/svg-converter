# Third-Party Notices

SVG Converter itself is released under the MIT License (see `LICENSE`).
The distributed application bundles the following third-party software.
Full license texts are included in the `licenses/` folder of each release zip.

| Component | License | Source |
|---|---|---|
| Qt 6 / PySide6 / Shiboken6 (6.12.0) | LGPL-3.0-only | https://code.qt.io/ , https://download.qt.io/official_releases/QtForPython/ |
| vtracer (0.6.15) | MIT | https://github.com/visioncortex/vtracer |
| Pillow (13.0.0) and the libraries it bundles (libjpeg, libpng, zlib, FreeType, etc.) | MIT-CMU and others (see `Pillow-LICENSE`) | https://github.com/python-pillow/Pillow |
| Python (3.12) | PSF License Agreement | https://www.python.org/ |
| PyInstaller bootloader | GPL-2.0-or-later with the Bootloader Exception, which permits distributing applications built with it under any license | https://github.com/pyinstaller/pyinstaller |

## Qt / PySide6 (LGPL-3.0)

Qt and PySide6 are used under the GNU Lesser General Public License v3
(`licenses/LGPL-3.0.txt`, which incorporates `licenses/GPL-3.0.txt`).
They are dynamically linked and shipped as separate, unmodified library files
(`_internal/PySide6` on Windows, `SvgConverter.app/Contents/Frameworks` on macOS),
so you may replace them with your own compatible build.
The application's own source code is available at https://github.com/bamtech1904/svg-converter ,
so you can also rebuild it against a modified Qt / PySide6 with the steps in `README.md`.
The Qt and PySide6 source code is available from the URLs above.
