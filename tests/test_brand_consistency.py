"""Brand colors and name are written once in shared/brand.json; every app's copy must match it."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRAND = json.loads((ROOT / "shared/brand.json").read_text())


def _web():
    css = (ROOT / "web/src/styles.css").read_text()
    root = css[css.index(":root") : css.index("}", css.index(":root"))]
    return {m[0]: m[1].upper() for m in re.findall(r"(--[a-z-]+):\s*(#[0-9a-fA-F]{6})", root)}


def _ios():
    swift = (ROOT / "ios/dinnerdesk/Theme.swift").read_text()
    out = {}
    for name, r, g, b in re.findall(r"static let (\w+) = Color\(red: (\d+) / 255, green: (\d+) / 255, blue: (\d+) / 255\)", swift):
        out[name] = "#%02X%02X%02X" % (int(r), int(g), int(b))
    for name, hexv in re.findall(r"static let (\w+) = Color\(hex: 0x([0-9a-fA-F]{6})\)", swift):
        out[name] = "#" + hexv.upper()
    return out


def _android():
    kt = (ROOT / "android/app/src/main/java/build/computerscience/dinnerdesk/ui/Theme.kt").read_text()
    return {name: "#" + hexv.upper() for name, hexv in re.findall(r"val (\w+) = Color\(0xFF([0-9a-fA-F]{6})\)", kt)}


def test_every_app_uses_the_brand_colors():
    apps = {"web": _web(), "ios": _ios(), "android": _android()}
    wrong = []
    for color, spec in BRAND["colors"].items():
        for app, found in apps.items():
            name = spec[app]
            if name is None:
                continue
            if name not in found:
                wrong.append(f"{app} has no {name} ({color})")
            elif found[name] != spec["hex"]:
                wrong.append(f"{app} {name} is {found[name]}, brand {color} is {spec['hex']}")
    assert not wrong, "Colors drifted from shared/brand.json:\n" + "\n".join(wrong)


def test_every_app_uses_the_brand_name():
    name = BRAND["name"]
    copy = json.loads((ROOT / "ios/dinnerdesk/copy.json").read_text())
    assert copy["app.name"] == name
    assert f"<title>{name}</title>" in (ROOT / "web/index.html").read_text()
    assert f'<string name="app_name">{name}</string>' in (
        ROOT / "android/app/src/main/res/values/strings.xml").read_text()


def test_ios_home_screen_names_use_the_brand_name():
    pbx = (ROOT / "ios/dinnerdesk.xcodeproj/project.pbxproj").read_text()
    names = set(re.findall(r'INFOPLIST_KEY_CFBundleDisplayName = "?([^";]+)"?;', pbx))
    assert names <= {BRAND["name"]}, f"iOS display names {names} != {BRAND['name']}"
