"""Dashboard palettes and a private, explicitly selected appearance preference."""
from __future__ import annotations

import json
from pathlib import Path

from textual.theme import Theme

from jobs.navidrome import atomic_write


THEME_CHOICES = (
    ("Nyx", "nyx-dark"),
    ("Catppuccin Mocha", "catppuccin-mocha"),
    ("AMOLED Black", "amoled-black"),
)
THEME_NAMES = tuple(name for _, name in THEME_CHOICES)
DEFAULT_THEME = "nyx-dark"

NYX_THEME = Theme(
    name="nyx-dark", primary="#bcb2ff", secondary="#83c9bb", accent="#bed5ff",
    foreground="#d8e0f0", background="#0c1222", surface="#15203a", panel="#101b30",
    warning="#d4b87c", error="#f38ba8", success="#83c9bb", dark=True,
    variables={"border": "#35446c", "footer-background": "#17213a",
               "button-color-foreground": "#0c1222"},
)

AMOLED_THEME = Theme(
    name="amoled-black", primary="#c4b5fd", secondary="#67e8d1", accent="#93c5fd",
    foreground="#eeeeef", background="#000000", surface="#000000", panel="#000000",
    boost="#101014", warning="#facc75", error="#fda4af", success="#86efac", dark=True,
    variables={"border": "#40404a", "border-blurred": "#303038",
               "footer-background": "#000000", "footer-key-foreground": "#c4b5fd",
               "block-cursor-background": "#c4b5fd", "block-cursor-foreground": "#000000",
               "button-color-foreground": "#000000"},
)


def load_theme(root: Path) -> str:
    """Read a bounded preference without creating state on startup."""
    try:
        with (root / "state" / "tui-preferences.json").open("rb") as handle:
            content = handle.read(4097)
        if len(content) > 4096:
            return DEFAULT_THEME
        value = json.loads(content)
        if isinstance(value, dict) and value.get("theme") in THEME_NAMES:
            return value["theme"]
    except (OSError, ValueError):
        pass
    return DEFAULT_THEME


def save_theme(root: Path, name: str) -> None:
    if name not in THEME_NAMES:
        raise ValueError("Unsupported dashboard theme")
    atomic_write(root / "state" / "tui-preferences.json", json.dumps({"theme": name}) + "\n")
