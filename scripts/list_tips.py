#!/usr/bin/env python3
"""List every in-app tip (developer only).

Tips are marked in the web code with a hidden `data-tip="<id>"` attribute on
the element that holds the tip text. Users never see the attribute; it is only
here so we can collect tips for a future feature.

Usage: python3 scripts/list_tips.py            # table of id, file:line, text
       python3 scripts/list_tips.py --json     # same, as JSON
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "src"
OPEN_TAG = re.compile(r'<(\w+)[^>]*\sdata-tip=(?:"([^"]+)"|\{`([^`]+)`\})[^>]*>')


def _text_after(src: str, start: int, tag: str) -> str:
    end = src.find(f"</{tag}>", start)
    raw = src[start:end if end != -1 else start + 400]
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def collect() -> list[dict]:
    tips = []
    for path in sorted(SRC.rglob("*.jsx")):
        src = path.read_text(encoding="utf-8")
        for m in OPEN_TAG.finditer(src):
            tag, plain, templ = m.group(1), m.group(2), m.group(3)
            tips.append(
                {
                    "id": plain or templ,
                    "file": str(path.relative_to(ROOT)),
                    "line": src.count("\n", 0, m.start()) + 1,
                    "text": _text_after(src, m.end(), tag),
                }
            )
    native = ROOT / "dinnerdesk" / "dinnerdesk"
    copy_path = native / "copy.json"
    if not copy_path.exists():
        copy_path = ROOT / "shared" / "copy.json"
    copy = json.loads(copy_path.read_text()) if copy_path.exists() else {}
    for path in sorted(native.glob("*.swift")):
        src = path.read_text()
        for m in re.finditer(r'\.accessibilityIdentifier\("tip\.([^"\n]+)"\)', src):
            key = m.group(1)
            tips.append({"id": key, "file": str(path.relative_to(ROOT)),
                         "line": src.count("\n", 0, m.start()) + 1,
                         "text": copy.get(key, key)})
    return tips


def main() -> int:
    tips = collect()
    if "--json" in sys.argv:
        print(json.dumps(tips, indent=2, ensure_ascii=False))
        return 0
    for t in tips:
        print(f"{t['id']:<32} {t['file']}:{t['line']}\n    {t['text']}")
    print(f"\n{len(tips)} tips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
