import customtkinter as ctk

APP_BACKGROUND = ("#f8fafc", "#0f1115")
SIDEBAR_COLOR = ("#f1f5f9", "#0b0d12")
SURFACE_PRIMARY = ("#ffffff", "#171b24")
SURFACE_SECONDARY = ("#f8fafc", "#111318")
SURFACE_TERTIARY = ("#eef2ff", "#222838")
TEXT_PRIMARY = ("#0f172a", "#f4f7fb")
TEXT_SECONDARY = ("#475569", "#9aa3b2")
BORDER_COLOR = ("#cbd5e1", "#2b3242")
ERROR_COLOR = ("#dc2626", "#f87171")
SUCCESS_COLOR = ("#16a34a", "#4ade80")
WARNING_COLOR = ("#d97706", "#facc15")
ACCENT_COLOR = ("#2563eb", "#2f6fed")
ACCENT_HOVER = ("#1d4ed8", "#245bd1")


def apply_theme(theme_name):
    ctk.set_appearance_mode(theme_name)
    ctk.set_default_color_theme("blue")
