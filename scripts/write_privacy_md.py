"""Write docs/PRIVACY.md from the privacy policy in ios/dinnerdesk/copy.json.

The policy is written once, in copy.json (privacy.policy.*), and every app shows it from there.
Run this after changing it: python3 scripts/write_privacy_md.py. tests/test_privacy_policy.py
fails if PRIVACY.md is out of date.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def render() -> str:
    copy = json.loads((ROOT / "ios/dinnerdesk/copy.json").read_text())
    app = copy["app.name"]
    text = lambda key: copy[key].replace("{app}", app)
    out = ["# Privacy policy", "", "<!-- Written by scripts/write_privacy_md.py from copy.json. Edit copy.json, not this file. -->",
           "", text("privacy.intro"), ""]
    for i in range(1, int(copy["privacy.policy.count"]) + 1):
        out += [f"## {text(f'privacy.policy.{i}.title')}", "", text(f"privacy.policy.{i}"), ""]
    return "\n".join(out)


if __name__ == "__main__":
    (ROOT / "docs/PRIVACY.md").write_text(render())
