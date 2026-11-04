"""Mobius sunset design tokens: native Qt, no external fonts or images.

The compact island has a black silhouette with a warm orange-to-red light
at its bottom edge. The feature deck uses graphite cards and just one
accent family, avoiding distracting rainbow styling.
"""
from PySide6.QtGui import QColor, QLinearGradient, QRadialGradient

BG = "#09090D"
SURFACE = "#141419"
SURFACE_RAISED = "#202027"
BORDER = "#34343D"
TEXT = "#FAF9FC"
MUTED = "#B6B1B5"
ORANGE = "#FF963E"
CORAL = "#FF6841"
RED = "#ED3950"
RED_DARK = "#BE264B"
DISABLED = "#56545A"

def gradient(start_x=0, start_y=0, end_x=100, end_y=0):
    g = QLinearGradient(start_x, start_y, end_x, end_y)
    g.setColorAt(0, QColor(ORANGE))
    g.setColorAt(.48, QColor(CORAL))
    g.setColorAt(1, QColor(RED))
    return g

def island_glow(cx, cy, radius):
    g = QRadialGradient(cx, cy, radius)
    g.setColorAt(0, QColor(255, 117, 54, 206))
    g.setColorAt(.38, QColor(250, 82, 62, 127))
    g.setColorAt(.78, QColor(229, 55, 74, 38))
    g.setColorAt(1, QColor(230, 35, 66, 0))
    return g
