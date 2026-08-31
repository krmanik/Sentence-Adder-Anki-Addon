#!/usr/bin/env python3
r"""Draw src/settings_icon.png, the gear shown next to the add button.

Run with the python inside Anki's program folder (it has PyQt6):

    QT_QPA_PLATFORM=offscreen \
    ~/Library/Application\ Support/AnkiProgramFiles/.venv/bin/python tools/make_settings_icon.py

Anki inverts editor button images in night mode, so the gear is drawn dark on
a transparent background like Anki's own buttons.
"""

import math
import os
import sys

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath

SIZE = 128
TEETH = 8
OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "settings_icon.png")


def gear_path(center, outer, inner, hole):
    path = QPainterPath()
    steps = TEETH * 4
    for step in range(steps):
        angle = 2 * math.pi * step / steps
        radius = outer if (step % 4) in (0, 1) else inner
        point = QPointF(center + radius * math.cos(angle),
                        center + radius * math.sin(angle))
        if step == 0:
            path.moveTo(point)
        else:
            path.lineTo(point)
    path.closeSubpath()
    path.addEllipse(QPointF(center, center), hole, hole)
    path.setFillRule(Qt.FillRule.OddEvenFill)
    return path


def main():
    QGuiApplication(sys.argv)

    image = QImage(SIZE, SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillPath(
        gear_path(SIZE / 2, SIZE * 0.46, SIZE * 0.36, SIZE * 0.15),
        QColor(35, 35, 35))
    painter.end()

    image.save(OUT, "PNG")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
