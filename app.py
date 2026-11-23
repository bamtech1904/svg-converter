"""PNG / JPEG → SVG 変換デスクトップアプリ。"""

import sys
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, Signal
from PIL import Image
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from converter import MAX_SIDE, SUPPORTED_SUFFIXES, Result, Settings, convert, load_rgba

PREVIEW_SIZE = 420


class _Signals(QObject):
    done = Signal(int, object, object)  # converter.Result, プレビュー用 QImage
    failed = Signal(int, str)


class ConvertJob(QRunnable):
    """変換は重いことがあるので、画面が固まらないよう別スレッドで動かす。"""

    def __init__(self, job_id: int, path: str, settings: Settings):
        super().__init__()
        self.job_id, self.path, self.settings = job_id, path, settings
        self.signals = _Signals()

    def run(self):
        try:
            result = convert(self.path, self.settings)
            if result.pixels is not None:
                # ドットモードの SVG は result.pixels と画素単位で一致する（test_pixel_mode.py で検証）。
                # 巨大な SVG を描き直すと Qt が数秒間 Python を止めるため、書き出した画素そのものを表示する
                preview = scale_preview(to_qimage(result.pixels), crisp=True)
            else:
                preview = render_svg(result.svg)
            self.signals.done.emit(self.job_id, result, preview)
        except Exception as e:  # 壊れた画像などは画面にメッセージを出す
            self.signals.failed.emit(self.job_id, str(e))


class Preview(QLabel):
    def __init__(self, placeholder: str):
        super().__init__(placeholder)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(PREVIEW_SIZE, PREVIEW_SIZE)
        self.setStyleSheet("border: 1px solid #999; background: #f4f4f4; color: #666;")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SVG Converter")
        self.setAcceptDrops(True)
        self.image_path: str | None = None
        self.source: QImage | None = None  # 左プレビュー用の元画像
        self.svg: str | None = None
        self.job_id = 0
        self.pool = QThreadPool.globalInstance()

        # スライダーを動かすたびに変換しないよう、止まってから少し待って変換する
        self.debounce = QTimer(self, singleShot=True, interval=300)
        self.debounce.timeout.connect(self.start_convert)

        open_btn = QPushButton("画像を開く…")
        open_btn.clicked.connect(self.open_dialog)
        self.save_btn = QPushButton("SVG を保存…")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_dialog)

        self.mode_box = QComboBox()
        self.mode_box.addItem("カラー", "color")
        self.mode_box.addItem("白黒", "binary")
        self.mode_box.addItem("ドット（画素そのまま）", "pixel")
        self.mode_box.currentIndexChanged.connect(self.update_controls)
        self.mode_box.currentIndexChanged.connect(self.schedule_convert)

        self.curve_box = QComboBox()
        self.curve_box.addItem("なめらか（曲線）", "spline")
        self.curve_box.addItem("カクカク（直線）", "polygon")
        self.curve_box.currentIndexChanged.connect(self.schedule_convert)

        self.speckle = self._slider(1, 64, 4)
        self.precision = self._slider(1, 8, 6)

        form = QFormLayout()
        form.addRow("色", self.mode_box)
        form.addRow("線", self.curve_box)
        form.addRow("ノイズ除去（右ほど単純）", self.speckle)
        form.addRow("色の細かさ（右ほど多色）", self.precision)

        buttons = QHBoxLayout()
        buttons.addWidget(open_btn)
        buttons.addWidget(self.save_btn)
        buttons.addStretch()

        self.before = Preview("ここに PNG / JPEG を\nドラッグ＆ドロップ")
        self.after = Preview("変換結果")
        previews = QHBoxLayout()
        previews.addWidget(self.before)
        previews.addWidget(self.after)

        self.status = QLabel("")

        root = QVBoxLayout()
        root.addLayout(buttons)
        root.addLayout(form)
        root.addLayout(previews)
        root.addWidget(self.status)
        container = QWidget()
        container.setLayout(root)
        self.setCentralWidget(container)

    def update_controls(self):
        # ドットモードは画素をそのまま書き出すので、トレース用の調整項目は効かない
        tracing = self.mode_box.currentData() != "pixel"
        for w in (self.curve_box, self.speckle, self.precision):
            w.setEnabled(tracing)
        self.show_source()

    def show_source(self):
        if self.source is not None:
            crisp = self.mode_box.currentData() == "pixel"
            self.before.setPixmap(QPixmap.fromImage(scale_preview(self.source, crisp)))

    def _slider(self, lo: int, hi: int, value: int) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(lo, hi)
        s.setValue(value)
        s.valueChanged.connect(self.schedule_convert)
        return s

    # --- 入力 ---
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        urls = e.mimeData().urls()
        if urls:
            self.load(urls[0].toLocalFile())

    def open_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "画像を開く", "", "画像 (*.png *.jpg *.jpeg)"
        )
        if path:
            self.load(path)

    def load(self, path: str):
        if Path(path).suffix.lower() not in SUPPORTED_SUFFIXES:
            QMessageBox.warning(self, "未対応の形式", "PNG か JPEG を選んでください。")
            return
        try:
            # 変換と同じ読み込み処理を使い、回転や色の解釈をそろえる
            image = to_qimage(load_rgba(path))
        except Exception:  # 壊れた画像・巨大すぎる画像など
            QMessageBox.warning(self, "読み込み失敗", "画像を開けませんでした。")
            return
        self.image_path = path
        self.source = image
        self.show_source()
        self.start_convert()

    # --- 変換 ---
    def schedule_convert(self):
        if self.image_path:
            self.save_btn.setEnabled(False)  # 設定と食い違う古い SVG を保存させない
            self.debounce.start()

    def start_convert(self):
        if not self.image_path:
            return
        self.debounce.stop()
        self.job_id += 1
        self.save_btn.setEnabled(False)
        self.status.setText("変換中…")
        settings = Settings(
            colormode=self.mode_box.currentData(),
            mode=self.curve_box.currentData(),
            filter_speckle=self.speckle.value(),
            color_precision=self.precision.value(),
        )
        job = ConvertJob(self.job_id, self.image_path, settings)
        job.signals.done.connect(self.on_done)
        job.signals.failed.connect(self.on_failed)
        self.pool.start(job)

    def on_done(self, job_id: int, result: Result, preview: QImage):
        if job_id != self.job_id:  # 設定変更で古くなった結果は捨てる
            return
        self.svg = result.svg
        self.after.setPixmap(QPixmap.fromImage(preview))
        if result.path_count == 0:
            self.save_btn.setEnabled(False)
            if result.pixels is not None:
                self.status.setText("透明な画素しかないため、書き出す図形がありません。")
            else:
                self.status.setText("図形が検出されませんでした。「色」や「ノイズ除去」を変えてみてください。")
            return
        self.save_btn.setEnabled(True)
        message = f"変換完了（SVG {len(result.svg) / 1024:.0f} KB）"
        if result.scaled:
            message += f"　※長辺 {MAX_SIDE}px に縮小して変換しました"
        self.status.setText(message)

    def on_failed(self, job_id: int, message: str):
        if job_id != self.job_id:
            return
        self.svg = None
        self.after.setText("変換に失敗しました")
        self.status.setText(message)

    # --- 保存 ---
    def save_dialog(self):
        # ダイアログ表示中に再変換で self.svg が変わっても、押した時点の結果を保存する
        svg = self.svg
        if not (svg and self.image_path):
            return
        default = str(Path(self.image_path).with_suffix(".svg"))
        path, _ = QFileDialog.getSaveFileName(self, "SVG を保存", default, "SVG (*.svg)")
        if not path:
            return
        try:
            Path(path).write_text(svg, encoding="utf-8")
        except OSError as e:
            QMessageBox.warning(self, "保存失敗", str(e))
            return
        self.status.setText(f"保存しました: {path}")


def to_qimage(img: Image.Image) -> QImage:
    rgba = img.convert("RGBA")
    w, h = rgba.size
    # copy(): QImage は bytes を参照するだけなので、bytes が消えても使えるよう複製する
    return QImage(rgba.tobytes(), w, h, w * 4, QImage.Format.Format_RGBA8888).copy()


def scale_preview(image: QImage, crisp: bool) -> QImage:
    """プレビュー枠に収まるよう拡大縮小する。crisp=True（ドットモード）は画素のマスを見せる。"""
    long_side = max(image.width(), image.height())
    if crisp and long_side <= PREVIEW_SIZE:
        # 補間せず整数倍で拡大し、画素のマスの大きさをそろえる
        f = PREVIEW_SIZE // long_side
        return image.scaled(
            image.width() * f, image.height() * f, mode=Qt.TransformationMode.FastTransformation
        )
    return image.scaled(
        PREVIEW_SIZE,
        PREVIEW_SIZE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def render_svg(svg: str) -> QImage:
    # 変換と同じ別スレッドで呼ぶ（QPixmap は画面側のスレッドでしか扱えないので QImage に描く）。
    # ただし描画中は Python の実行が止まるため、巨大な SVG では別スレッドでも画面は固まる
    renderer = QSvgRenderer(svg.encode())
    size = renderer.defaultSize()
    size.scale(PREVIEW_SIZE, PREVIEW_SIZE, Qt.AspectRatioMode.KeepAspectRatio)
    image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return image


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
