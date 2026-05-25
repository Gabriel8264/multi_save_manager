import customtkinter as ctk

SURFACE_PRIMARY = ("#ffffff", "#111827")
SURFACE_SECONDARY = ("#f8fafc", "#0f172a")
SURFACE_TERTIARY = ("#eef2ff", "#172033")
TEXT_PRIMARY = ("#0f172a", "#f8fafc")
TEXT_SECONDARY = ("#475569", "#94a3b8")
BORDER_COLOR = ("#cbd5e1", "#334155")
ERROR_COLOR = ("#dc2626", "#f87171")
SUCCESS_COLOR = ("#16a34a", "#4ade80")
WARNING_COLOR = ("#d97706", "#facc15")
ACCENT_COLOR = ("#2563eb", "#3b82f6")
ACCENT_HOVER = ("#1d4ed8", "#2563eb")


def apply_theme(theme_name):
    ctk.set_appearance_mode(theme_name)
    ctk.set_default_color_theme("blue")
