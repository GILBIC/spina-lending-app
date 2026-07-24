"""Display-only light/dark color palettes shared by SPINA UI sections."""


def _spina_v20_dash_palette(self=None):
    try:
        theme = str(getattr(self, "ui_theme", "dark") or "dark").lower()
    except Exception:
        theme = "dark"

    if theme.startswith("l"):
        return {
            "chart": "#111827",
            "fg": "#111827",
            "chart_fg": "#ffffff",
            "chart_muted": "#d1d5db",
            "track": "#334155",
            "blue": "#3b82f6",
            "green": "#22c55e",
            "yellow": "#f59e0b",
            "orange": "#fb923c",
            "red": "#ef4444",
            "purple": "#8b5cf6",
            "panel": "#ffffff",
            "border": "#d6dde8",
        }

    return {
        "chart": "#111827",
        "fg": "#f8fafc",
        "chart_fg": "#ffffff",
        "chart_muted": "#cbd5e1",
        "track": "#334155",
        "blue": "#60a5fa",
        "green": "#22c55e",
        "yellow": "#fbbf24",
        "orange": "#fb923c",
        "red": "#fb7185",
        "purple": "#a78bfa",
        "panel": "#171a23",
        "border": "#343b4d",
    }


def _spina_v21_cash_colors(self=None):
    try:
        theme = str(getattr(self, "ui_theme", "dark") or "dark").lower()
    except Exception:
        theme = "dark"

    if theme.startswith("l"):
        return {
            "bg": "#f3f6fb",
            "panel": "#ffffff",
            "card": "#ffffff",
            "card2": "#f8fafc",
            "chart": "#111827",
            "border": "#d6dde8",
            "fg": "#111827",
            "muted": "#64748b",
            "chart_fg": "#ffffff",
            "chart_muted": "#cbd5e1",
            "blue": "#2563eb",
            "green": "#16a34a",
            "yellow": "#d97706",
            "orange": "#ea580c",
            "red": "#dc2626",
            "purple": "#7c3aed",
            "cyan": "#0891b2",
            "track": "#334155",
            "soft": "#e8eef7",
            "button": "#2563eb",
        }

    return {
        "bg": "#0f1117",
        "panel": "#171a23",
        "card": "#20232d",
        "card2": "#262a36",
        "chart": "#111827",
        "border": "#343b4d",
        "fg": "#f8fafc",
        "muted": "#aab3c2",
        "chart_fg": "#ffffff",
        "chart_muted": "#cbd5e1",
        "blue": "#60a5fa",
        "green": "#22c55e",
        "yellow": "#fbbf24",
        "orange": "#fb923c",
        "red": "#fb7185",
        "purple": "#a78bfa",
        "cyan": "#22d3ee",
        "track": "#334155",
        "soft": "#252b38",
        "button": "#3b82f6",
    }


def _spina_v24_cilog_colors(self=None):
    try:
        theme = str(getattr(self, "ui_theme", "dark") or "dark").lower()
    except Exception:
        theme = "dark"

    if theme.startswith("l"):
        return {
            "bg": "#f3f6fb",
            "panel": "#ffffff",
            "card": "#ffffff",
            "card2": "#f8fafc",
            "chart": "#111827",
            "border": "#d6dde8",
            "fg": "#111827",
            "muted": "#64748b",
            "chart_fg": "#ffffff",
            "chart_muted": "#cbd5e1",
            "blue": "#2563eb",
            "green": "#16a34a",
            "orange": "#ea580c",
            "purple": "#7c3aed",
            "red": "#dc2626",
            "yellow": "#d97706",
            "soft": "#e8eef7",
            "track": "#334155",
        }

    return {
        "bg": "#0f1117",
        "panel": "#171a23",
        "card": "#20232d",
        "card2": "#262a36",
        "chart": "#111827",
        "border": "#343b4d",
        "fg": "#f8fafc",
        "muted": "#aab3c2",
        "chart_fg": "#ffffff",
        "chart_muted": "#cbd5e1",
        "blue": "#60a5fa",
        "green": "#22c55e",
        "orange": "#fb923c",
        "purple": "#a78bfa",
        "red": "#fb7185",
        "yellow": "#fbbf24",
        "soft": "#252b38",
        "track": "#334155",
    }


def _spina_v22_reports_colors(self=None):
    try:
        theme = str(getattr(self, "ui_theme", "dark") or "dark").lower()
    except Exception:
        theme = "dark"

    if theme.startswith("l"):
        return {
            "bg": "#f3f6fb",
            "panel": "#ffffff",
            "card": "#ffffff",
            "card2": "#f8fafc",
            "border": "#d6dde8",
            "fg": "#111827",
            "muted": "#64748b",
            "blue": "#2563eb",
            "green": "#16a34a",
            "orange": "#ea580c",
            "purple": "#7c3aed",
            "red": "#dc2626",
            "soft": "#e8eef7",
            "entry": "#ffffff",
        }

    return {
        "bg": "#0f1117",
        "panel": "#171a23",
        "card": "#20232d",
        "card2": "#262a36",
        "border": "#343b4d",
        "fg": "#f8fafc",
        "muted": "#aab3c2",
        "blue": "#60a5fa",
        "green": "#22c55e",
        "orange": "#fb923c",
        "purple": "#a78bfa",
        "red": "#fb7185",
        "soft": "#252b38",
        "entry": "#111827",
    }


def _spina_v25_collector_colors(self=None):
    try:
        theme = str(getattr(self, "ui_theme", "dark") or "dark").lower()
    except Exception:
        theme = "dark"

    if theme.startswith("l"):
        return {
            "bg": "#f3f6fb",
            "panel": "#ffffff",
            "card": "#ffffff",
            "card2": "#f8fafc",
            "border": "#d6dde8",
            "fg": "#111827",
            "muted": "#64748b",
            "blue": "#2563eb",
            "green": "#16a34a",
            "orange": "#ea580c",
            "purple": "#7c3aed",
            "red": "#dc2626",
            "yellow": "#d97706",
            "soft": "#e8eef7",
            "entry": "#ffffff",
        }

    return {
        "bg": "#0f1117",
        "panel": "#171a23",
        "card": "#20232d",
        "card2": "#262a36",
        "border": "#343b4d",
        "fg": "#f8fafc",
        "muted": "#aab3c2",
        "blue": "#60a5fa",
        "green": "#22c55e",
        "orange": "#fb923c",
        "purple": "#a78bfa",
        "red": "#fb7185",
        "yellow": "#fbbf24",
        "soft": "#252b38",
        "entry": "#111827",
    }


def _spina_v17_dash_colors(self=None):
    """Dashboard-specific modern colors that work in light and dark mode."""
    try:
        theme = str(getattr(self, "ui_theme", "dark") or "dark").lower()
    except Exception:
        theme = "dark"

    if theme.startswith("l"):
        return {
            "bg": "#f4f7fb",
            "panel": "#ffffff",
            "card": "#ffffff",
            "card2": "#f8fafc",
            "border": "#d8e0ea",
            "fg": "#111827",
            "muted": "#64748b",
            "accent": "#2563eb",
            "accent2": "#16a34a",
            "warn": "#d97706",
            "danger": "#dc2626",
            "soft": "#e8eef7",
            "track": "#e5e7eb",
            "bar": "#2563eb",
            "bar2": "#7c3aed",
        }

    return {
        "bg": "#111217",
        "panel": "#181a21",
        "card": "#20232d",
        "card2": "#262a36",
        "border": "#343946",
        "fg": "#f8fafc",
        "muted": "#aab2c0",
        "accent": "#60a5fa",
        "accent2": "#4ade80",
        "warn": "#fbbf24",
        "danger": "#fb7185",
        "soft": "#2b3040",
        "track": "#343946",
        "bar": "#60a5fa",
        "bar2": "#c084fc",
    }


def _spina_v18_dashboard_palette(self=None):
    try:
        theme = str(getattr(self, "ui_theme", "dark") or "dark").lower()
    except Exception:
        theme = "dark"

    if theme.startswith("l"):
        return {
            "bg": "#f3f6fb",
            "panel": "#ffffff",
            "chart": "#111827",
            "chart2": "#172033",
            "fg": "#111827",
            "muted": "#64748b",
            "chart_fg": "#f8fafc",
            "chart_muted": "#cbd5e1",
            "border": "#d6dde8",
            "track": "#334155",
            "track2": "#e5e7eb",
            "blue": "#3b82f6",
            "green": "#22c55e",
            "yellow": "#f59e0b",
            "orange": "#fb923c",
            "red": "#ef4444",
            "purple": "#8b5cf6",
            "cyan": "#06b6d4",
        }

    return {
        "bg": "#0f1117",
        "panel": "#171a23",
        "chart": "#111827",
        "chart2": "#151d2c",
        "fg": "#f8fafc",
        "muted": "#aab3c2",
        "chart_fg": "#f8fafc",
        "chart_muted": "#cbd5e1",
        "border": "#343b4d",
        "track": "#334155",
        "track2": "#252b38",
        "blue": "#60a5fa",
        "green": "#22c55e",
        "yellow": "#fbbf24",
        "orange": "#fb923c",
        "red": "#fb7185",
        "purple": "#a78bfa",
        "cyan": "#22d3ee",
    }

# Login color palette extracted in Wave 25.

def _spina_v32_login_colors(self=None):
    try:
        theme = str(getattr(self, "ui_theme", "dark") or "dark").lower()
    except Exception:
        theme = "dark"

    if theme.startswith("l"):
        return {
            "bg": "#f3f6fb",
            "left": "#111827",
            "panel": "#ffffff",
            "card": "#ffffff",
            "card2": "#f8fafc",
            "border": "#d6dde8",
            "fg": "#111827",
            "muted": "#64748b",
            "left_fg": "#ffffff",
            "left_muted": "#cbd5e1",
            "blue": "#2563eb",
            "green": "#16a34a",
            "red": "#dc2626",
            "soft": "#e8eef7",
        }

    return {
        "bg": "#0f1117",
        "left": "#111827",
        "panel": "#171a23",
        "card": "#20232d",
        "card2": "#262a36",
        "border": "#343b4d",
        "fg": "#f8fafc",
        "muted": "#aab3c2",
        "left_fg": "#ffffff",
        "left_muted": "#cbd5e1",
        "blue": "#60a5fa",
        "green": "#22c55e",
        "red": "#fb7185",
        "soft": "#252b38",
    }
