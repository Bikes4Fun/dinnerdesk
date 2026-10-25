"""Every tab's title comes from TabHeader (ios/dinnerdesk/Theme.swift), so tabs can't drift apart
in font, color or position again."""
from pathlib import Path
import re

IOS = Path(__file__).resolve().parents[1] / "ios" / "dinnerdesk"
TABS = ["PlanView.swift", "RecipesView.swift", "GroceryView.swift", "PrepView.swift", "MoreView.swift"]
# Full-screen welcome titles that aren't tabs.
BIG_TITLE_ELSEWHERE = {"Theme.swift", "AuthView.swift", "TourView.swift"}


def _main_view(name: str) -> str:
    """The tab's own struct, up to the next top-level declaration."""
    source = "\n".join(l for l in (IOS / name).read_text().split("\n") if not l.strip().startswith("//"))
    struct = name.removesuffix(".swift")
    start = source.index(f"struct {struct}: View")
    end = re.search(r"^(?:private )?(?:struct|extension|enum|final class) ", source[start + 1:], re.M)
    return source[start:start + 1 + end.start()] if end else source[start:]


def test_every_tab_uses_tab_header():
    for name in TABS:
        view = _main_view(name)
        assert "TabHeader(" in view, f"{name} must title itself with TabHeader"
        assert "largeNavigationTitle()" not in view, f"{name} uses the system title instead of TabHeader"


def test_only_tab_header_styles_page_titles():
    for path in IOS.glob("*.swift"):
        if path.name not in BIG_TITLE_ELSEWHERE:
            assert "Theme.bigTitle" not in path.read_text(), f"{path.name} styles a page title itself; use TabHeader"
