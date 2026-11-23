"""A phrase people see in more than one app is written once, in ios/dinnerdesk/copy.json.

Fails when a new phrase is typed out in two or more of web, iOS and Android instead of using
Copy.text(...). Phrases that must stay typed (constants, case labels, files the Apple Watch also
compiles, generated option files) are listed in tests/shared_phrases_allowed.txt.
After adding a phrase to copy.json and using Copy.text in each app, this passes again.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = ROOT / "tests/shared_phrases_allowed.txt"
STR = re.compile(r'(?<![\\\w])"((?:[^"\\\n]|\\.){6,})"')
JSX = re.compile(r">\s*([^<>{}\n]{6,}?)\s*<")


def _norm(text):
    return re.sub(r"\s+", " ", text.replace("’", "'").replace('\\"', '"')).strip()


def _visible(text):
    return (len(text) >= 6 and text[0].isupper() and re.search(r"[A-Za-z]{2,} [A-Za-z]", text)
            and not re.search(r"[{}<>=_\\$`|]|https?:|\.(jsx?|swift|kt|png|json)\b", text))


def _phrases(paths, jsx=False):
    found = set()
    for path in paths:
        for line in path.read_text(encoding="utf-8").split("\n"):
            stripped = line.lstrip()
            if stripped.startswith(("//", "*", "/*")):
                continue
            for m in STR.finditer(line):
                if "\\(" not in m.group(1) and "$" not in m.group(1) and _visible(_norm(m.group(1))):
                    found.add(_norm(m.group(1)))
            if jsx:
                for m in JSX.finditer(line):
                    if "&" not in m.group(1) and _visible(_norm(m.group(1))):
                        found.add(_norm(m.group(1)))
    return found


def typed_in_two_apps():
    web = _phrases([p for p in (ROOT / "web/src").rglob("*.js*") if ".test." not in p.name], jsx=True)
    ios = _phrases((ROOT / "ios/dinnerdesk").glob("*.swift"))
    android = _phrases((ROOT / "android/app/src/main/java").rglob("*.kt"))
    return {t for t in web | ios | android if (t in web) + (t in ios) + (t in android) >= 2}


def test_no_new_phrase_is_typed_in_two_apps():
    allowed = {line for line in ALLOWED.read_text(encoding="utf-8").split("\n") if line and not line.startswith("#")}
    new = sorted(typed_in_two_apps() - allowed)
    assert not new, ("These phrases are typed in two or more apps. Add each to ios/dinnerdesk/copy.json and "
                     "use Copy.text(...) in every app:\n" + "\n".join(new))
