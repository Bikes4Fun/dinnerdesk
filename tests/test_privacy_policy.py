"""The privacy policy is written once, in copy.json, and shown from there on web, iOS and Android."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_privacy_md_matches_copy_json():
    import importlib.util
    spec = importlib.util.spec_from_file_location("w", ROOT / "scripts/write_privacy_md.py")
    w = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(w)
    assert (ROOT / "docs/PRIVACY.md").read_text() == w.render(), "Run python3 scripts/write_privacy_md.py"


def test_every_policy_section_has_a_title_and_body():
    copy = json.loads((ROOT / "ios/dinnerdesk/copy.json").read_text())
    for i in range(1, int(copy["privacy.policy.count"]) + 1):
        assert copy[f"privacy.policy.{i}.title"].strip()
        assert copy[f"privacy.policy.{i}"].strip()


def test_no_app_keeps_its_own_copy_of_the_policy():
    # A sentence only the policy has; if it shows up in app code, someone pasted the policy back in.
    marker = "We store a hash of the reset link"
    for path in ["web/src/pages/Privacy.jsx", "ios/dinnerdesk/SettingsView.swift",
                 "android/app/src/main/java/build/computerscience/dinnerdesk/ui/SettingsView.kt"]:
        assert marker not in (ROOT / path).read_text(), f"{path} has its own copy of the privacy policy"
