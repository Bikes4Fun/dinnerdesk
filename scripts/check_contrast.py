#!/usr/bin/env python3
"""Check that theme text colors meet WCAG AA (4.5:1) on every background they sit on.

The palette is shared by web (styles.css), iOS (Theme.swift) and Android (Theme.kt), so one
check covers all three. Run it after changing any palette color:

    python3 scripts/check_contrast.py

Exits non-zero and names the failing pair, so this can gate a release. Only pairs the apps
really use are listed; "muted on coral" is not here because coral is a fill that only ever
carries aubergine (see claude/dinnerdesk-palette.md).
"""
from __future__ import annotations

import sys

TEXT = {
    "ink": "#2E1A2C",
    "muted": "#746570",
    "accent (deep coral)": "#B84228",
    "aubergine": "#4A1646",
    "coralInk": "#8A3A22",
    "ok": "#3F6B4A",
    "danger": "#B33B32",
}
# Backgrounds that carry body text. Coral (#FA7E5A) is a fill for circles and dots, never a
# text background, so it is checked separately below.
BACKGROUNDS = {
    "page": "#FFFBF6",
    "surface": "#FFFDF9",
    "chip / aubergine tint": "#F1E7EF",
    "pill": "#F6EEF5",
    "coral tint": "#FDE6DD",
    "soft": "#F3EBE8",
}
# Pairs where the text color is fixed by design rather than drawn from the table above.
EXTRA = [
    ("aubergine on coral fill", "#4A1646", "#FA7E5A"),
    ("cream on aubergine button", "#FBF6EE", "#4A1646"),
    ("white on danger", "#FFFFFF", "#B33B32"),
]
MIN_RATIO = 4.5


def luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def ratio(foreground: str, background: str) -> float:
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def main() -> int:
    failures: list[str] = []
    for text_name, text_color in TEXT.items():
        for bg_name, bg_color in BACKGROUNDS.items():
            found = ratio(text_color, bg_color)
            if found < MIN_RATIO:
                failures.append(f"{text_name} on {bg_name}: {found:.2f}:1 (needs {MIN_RATIO}:1)")
    for label, text_color, bg_color in EXTRA:
        found = ratio(text_color, bg_color)
        if found < MIN_RATIO:
            failures.append(f"{label}: {found:.2f}:1 (needs {MIN_RATIO}:1)")

    if failures:
        print("Contrast failures:")
        for failure in failures:
            print(f"  {failure}")
        return 1
    checked = len(TEXT) * len(BACKGROUNDS) + len(EXTRA)
    print(f"All {checked} color pairs meet {MIN_RATIO}:1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
