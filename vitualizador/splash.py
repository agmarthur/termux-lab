"""Tela de abertura animada: um terminal com o nome Termux Lab."""

from __future__ import annotations

import math

from PyQt6.QtCore import QElapsedTimer, QPointF, QPropertyAnimation, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import QWidget

from .theme import BG, BORDER, GREEN, GREEN_DARK, TEXT, TEXT_DIM

DURATION = 3000          # ms até começar o fade
FADE = 380               # ms do fade final


class Splash(QWidget):
    finished = pyqtSignal()

    def __init__(self, n_arches: int = 0, kvm: bool = False) -> None:
        super().__init__(
            None,
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(680, 420)
        self.setWindowTitle("Termux Lab")

        self.n_arches = n_arches
        self.kvm = kvm
        self.elapsed = 0
        self._done = False

        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._clock = QElapsedTimer()

        self.boot_lines = [
            ("inicializando subsistema QEMU", "ok"),
            ("detectando arquiteturas", str(n_arches) if n_arches else "—"),
            ("acelerador KVM", "ativo" if kvm else "indisponível"),
            ("carregando perfis de máquinas", "ok"),
        ]

        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.center() - self.rect().center())

    # ------------------------------------------------------------- animação

    def start(self) -> None:
        self._clock.start()
        self._timer.start()

    def _tick(self) -> None:
        self.elapsed = self._clock.elapsed()
        self.update()
        if self.elapsed >= DURATION and not self._done:
            self._fade_out()

    def _fade_out(self) -> None:
        self._done = True
        self._timer.stop()
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(FADE)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.finished.connect(self._emit_finished)
        self._anim.start()

    def _emit_finished(self) -> None:
        self.finished.emit()
        self.close()

    def skip(self) -> None:
        if self._done:
            return
        self._done = True
        self._timer.stop()
        self._emit_finished()

    def closeEvent(self, event) -> None:  # noqa: N802 (API Qt)
        if not self._done:
            self._done = True
            self._timer.stop()
            self.finished.emit()
        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802 (API Qt)
        self.skip()

    def keyPressEvent(self, event) -> None:  # noqa: N802 (API Qt)
        self.skip()

    # ---------------------------------------------------------------- pintura

    def paintEvent(self, event) -> None:  # noqa: N802 (API Qt)
        t = self.elapsed
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # --- corpo e barra de título
        frame = QPainterPath()
        frame.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 14, 14)
        p.fillPath(frame, QColor("#0b0f14"))
        p.save()
        p.setClipPath(frame)
        p.fillRect(QRectF(0, 0, w, 42), QColor("#161b22"))
        p.restore()

        for i, color in enumerate(("#ff5f57", "#febc2e", "#28c840")):
            r = 5.2 + 0.7 * math.sin(t / 260 + i * 1.7)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(color))
            p.drawEllipse(QPointF(24 + i * 19, 21), r, r)

        p.setPen(QColor(TEXT_DIM))
        small = self._mono(11)
        p.setFont(small)
        p.drawText(QRectF(86, 8, w - 200, 26), Qt.AlignmentFlag.AlignVCenter,
                   "termux lab — terminal")

        # contador de arquiteturas no canto direito da barra
        if self.n_arches and t > 1700:
            p.setPen(QColor(GREEN))
            p.drawText(QRectF(w - 190, 8, 170, 26),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       f"{self.n_arches} arquiteturas")

        # --- nome digitado
        name = "termux lab"
        typed = self._typed(name, start=260, per_char=95)
        name_font = self._mono(36, bold=True, spacing=4.0)
        p.setFont(name_font)
        p.setPen(QColor(GREEN))
        p.drawText(QPointF(38, 128), typed)

        fm = p.fontMetrics()
        cursor_x = 38 + fm.horizontalAdvance(typed if typed else " ")
        if t < 1500 or (t // 520) % 2 == 0:
            p.fillRect(QRectF(cursor_x + 4, 96, 15, 36), QColor(GREEN).lighter(105))

        # --- linha de prompt
        prompt_font = self._mono(13)
        p.setFont(prompt_font)
        fm = p.fontMetrics()
        x = 38.0
        y = 176.0
        for text, color in (("visitor@termuxlab", GREEN), (":", TEXT_DIM),
                            ("~", "#58a6ff"), ("$ ", TEXT_DIM)):
            p.setPen(QColor(color))
            p.drawText(QPointF(x, y), text)
            x += fm.horizontalAdvance(text)

        cmd = self._typed("./termux-lab --gui", start=1330, per_char=22)
        p.setPen(QColor(TEXT))
        p.drawText(QPointF(x, y), cmd)
        if cmd:
            x += fm.horizontalAdvance(cmd)
            if (t // 400) % 2 == 0:
                p.fillRect(QRectF(x + 2, y - 12, 8, 15), QColor(TEXT_DIM))

        # --- linhas de boot
        line_font = self._mono(12)
        p.setFont(line_font)
        fm = p.fontMetrics()
        for i, (label, value) in enumerate(self.boot_lines):
            start = 1650 + i * 220
            if t < start:
                continue
            p.setOpacity(min(1.0, (t - start) / 180))
            ty = 226 + i * 25
            p.setPen(QColor(TEXT_DIM))
            p.drawText(QPointF(38, ty), label)
            label_w = fm.horizontalAdvance(label)
            dots_x = 38 + label_w + 6
            dots_end = w - 150
            if dots_end > dots_x:
                step = 7
                count = int((dots_end - dots_x) / step)
                p.setPen(QColor("#2d333b"))
                for d in range(count):
                    p.drawPoint(QPointF(dots_x + d * step, ty - 4))
            p.setPen(QColor(GREEN))
            p.drawText(QRectF(w - 176, ty - 15, 140, 20),
                       Qt.AlignmentFlag.AlignRight, value)
            p.setOpacity(1.0)

        # --- barra de progresso
        bar = QRectF(38, h - 62, w - 76, 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#21262d"))
        p.drawRoundedRect(bar, 3, 3)
        progress = min(1.0, t / DURATION)
        if progress > 0:
            p.setBrush(QColor(GREEN_DARK).lighter(115))
            p.drawRoundedRect(QRectF(bar.x(), bar.y(), bar.width() * progress, bar.height()),
                              3, 3)

        p.setFont(self._mono(10))
        p.setPen(QColor("#484f58"))
        p.drawText(QPointF(38, h - 32), "carregando interface")
        p.drawText(QRectF(w - 210, h - 43, 172, 16),
                   Qt.AlignmentFlag.AlignRight, "clique para pular")

        # --- borda
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 14, 14)

        p.end()

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _mono(size: int, bold: bool = False, spacing: float = 0.0) -> QFont:
        font = QFont("monospace")
        font.setStyleHint(QFont.StyleHint.TypeWriter)
        font.setPixelSize(size)
        font.setBold(bold)
        if spacing:
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
        return font

    def _typed(self, text: str, start: int, per_char: int) -> str:
        if self.elapsed < start:
            return ""
        count = (self.elapsed - start) // per_char
        return text[:max(0, min(len(text), int(count)))]
