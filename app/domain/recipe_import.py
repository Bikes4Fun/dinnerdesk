"""Read a recipe off a public web page into a draft the cook reviews before saving.

Most recipe sites publish a schema.org Recipe as ld+json for search engines; this is the
same reader the catalog scrapers use (dd_support/scrapers/scrape_allrecipes.py). Name,
servings, time, ingredient lines, steps and the photo's link. Nothing is saved here; POST
/api/recipes saves what the cook keeps, with a private copy of the photo for that kitchen.
"""

from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
from urllib.parse import urljoin, urlparse

import httpx

from app.domain.grocery import split_ingredient_line

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Dinnerdesk-import"
)
MAX_BYTES = 4_000_000
MAX_PHOTO_BYTES = 5_000_000
MAX_REDIRECTS = 5
TIMEOUT = 15.0

LD_JSON_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
TAG_RE = re.compile(r"<[^>]+>")
DURATION_RE = re.compile(
    r"^P(?:(?P<d>\d+(?:\.\d+)?)D)?(?:T(?:(?P<h>\d+(?:\.\d+)?)H)?(?:(?P<m>\d+(?:\.\d+)?)M)?(?:(?P<s>\d+(?:\.\d+)?)S)?)?$",
    re.I,
)


class RecipeImportError(Exception):
    """A page the cook can't import. `code` is stable; the message is for people."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _public_host(host: str) -> bool:
    """Only fetch hosts on the public internet, never the server's own network."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global or ip.is_multicast:
            return False
    return bool(infos)


def _check_url(url: str) -> str:
    url = (url or "").strip()
    if url and "://" not in url:
        url = "https://" + url
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise RecipeImportError("bad_url", "That doesn't look like a web address.")
    if parts.port not in (None, 80, 443):
        raise RecipeImportError("bad_url", "That doesn't look like a public recipe page.")
    if not _public_host(parts.hostname):
        raise RecipeImportError("bad_url", "That doesn't look like a public recipe page.")
    return url


def _get(url: str, accept: str, max_bytes: int) -> tuple[bytes, str, str]:
    """GET a public URL, following redirects only to other public URLs.

    Returns (body, final url, content type)."""
    url = _check_url(url)
    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": USER_AGENT, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"},
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                with client.stream("GET", url) as response:
                    if response.is_redirect:
                        url = _check_url(urljoin(url, response.headers.get("location", "")))
                        continue
                    if response.status_code in (401, 403, 429):
                        raise RecipeImportError(
                            "blocked",
                            "That site doesn't let apps read its pages. You can type the recipe in instead.",
                        )
                    if response.status_code >= 400:
                        raise RecipeImportError(
                            "fetch_failed",
                            f"That site answered with an error ({response.status_code}).",
                        )
                    body = b""
                    for chunk in response.iter_bytes():
                        body += chunk
                        if len(body) > max_bytes:
                            raise RecipeImportError("too_big", "That page is too big to read.")
                    kind = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    return body, url, kind
            except httpx.HTTPError as exc:
                raise RecipeImportError("fetch_failed", "Couldn't reach that site.") from exc
    raise RecipeImportError("fetch_failed", "That page redirected too many times.")


def fetch_page(url: str) -> tuple[str, str]:
    """A public page's HTML and its final URL."""
    body, final_url, _kind = _get(url, "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8", MAX_BYTES)
    return body.decode("utf-8", errors="replace"), final_url


def fetch_image(url: str) -> bytes:
    """A recipe page's photo, for the kitchen's private copy (POST /recipes)."""
    body, _url, kind = _get(url, "image/jpeg,image/png,image/webp,image/*;q=0.8", MAX_PHOTO_BYTES)
    if not kind.startswith("image/"):
        raise RecipeImportError("not_image", "That link isn't a photo.")
    return body


def image_of(node) -> str:
    """The first photo in schema.org `image`: a URL, an ImageObject, or a list of either."""
    for item in _as_list(node):
        if isinstance(item, dict):
            item = item.get("url") or item.get("contentUrl")
        if isinstance(item, str) and item.strip() and not item.strip().lower().startswith("data:"):
            return item.strip()
    return ""


def _photo_link(page_url: str, raw: str) -> str:
    link = urljoin(page_url, raw) if raw else ""
    return link if link.lower().startswith(("http://", "https://")) else ""


def _as_list(node) -> list:
    if node is None:
        return []
    return node if isinstance(node, list) else [node]


def _is_type(node: dict, type_name: str) -> bool:
    return type_name in _as_list(node.get("@type"))


def extract_recipe_ld(page: str) -> dict | None:
    """The first schema.org Recipe in the page's ld+json, at the top or inside an @graph."""
    for match in LD_JSON_RE.finditer(page):
        try:
            data = json.loads(match.group(1).strip(), strict=False)
        except json.JSONDecodeError:
            continue
        for node in _as_list(data):
            if not isinstance(node, dict):
                continue
            if _is_type(node, "Recipe"):
                return node
            for g in _as_list(node.get("@graph")):
                if isinstance(g, dict) and _is_type(g, "Recipe"):
                    return g
    return None


def _clean(text) -> str:
    if not isinstance(text, str):
        return ""
    text = html.unescape(TAG_RE.sub(" ", html.unescape(text)))
    return re.sub(r"\s+([.,;:!?)])", r"\1", re.sub(r"\s+", " ", text)).strip()


def duration_minutes(value) -> int | None:
    """ISO 8601 duration (PT1H30M) to whole minutes."""
    m = DURATION_RE.match(str(value or "").strip())
    if not m or not any(m.groupdict().values()):
        return None
    g = {k: float(v or 0) for k, v in m.groupdict().items()}
    total = g["d"] * 1440 + g["h"] * 60 + g["m"] + g["s"] / 60
    return round(total) or None


def servings_of(value) -> int | None:
    """recipeYield is '4', 4, '4 servings', ['4', '4 servings'] or 'Makes 12 cookies'."""
    for item in _as_list(value):
        m = re.search(r"\d+", str(item))
        if m:
            n = int(m.group(0))
            if 1 <= n <= 50:
                return n
    return None


def _steps(node) -> list[str]:
    out: list[str] = []
    for item in _as_list(node):
        if isinstance(item, str):
            out.extend(line for line in (_clean(x) for x in re.split(r"\n+", item)) if line)
        elif isinstance(item, dict):
            if _is_type(item, "HowToSection") or "itemListElement" in item:
                out.extend(_steps(item.get("itemListElement")))
            else:
                text = _clean(item.get("text") or item.get("name"))
                if text:
                    out.append(text)
    return out


def normalize(ld: dict, source_url: str) -> dict:
    """Draft shaped like POST /api/recipes, plus the raw ingredient lines for editing."""
    lines = [_clean(x) for x in _as_list(ld.get("recipeIngredient") or ld.get("ingredients"))]
    lines = [x for x in lines if x]
    ingredients = []
    for line in lines:
        qty, name = split_ingredient_line(line)
        ingredients.append({"quantity": qty, "name": name or line})
    minutes = duration_minutes(ld.get("totalTime"))
    if minutes is None:
        parts = [duration_minutes(ld.get("prepTime")), duration_minutes(ld.get("cookTime"))]
        minutes = sum(p for p in parts if p) or None
    return {
        "name": _clean(ld.get("name") or ld.get("headline"))[:200],
        "servings": servings_of(ld.get("recipeYield")) or 4,
        "cooking_minutes": min(minutes, 24 * 60) if minutes else None,
        "source_url": source_url,
        # The site's photo. Shown in the form as a preview; POST /recipes copies it for the
        # kitchen and keeps this link as a fallback.
        "image_url": _photo_link(source_url, image_of(ld.get("image"))),
        "ingredient_lines": lines,
        "ingredients": ingredients,
        "instructions": [{"text": s, "prep": False, "ings": ""} for s in _steps(ld.get("recipeInstructions"))],
    }


def import_recipe(url: str) -> dict:
    page, final_url = fetch_page(url)
    ld = extract_recipe_ld(page)
    if not ld:
        raise RecipeImportError(
            "no_recipe",
            "Couldn't find a recipe on that page. You can type it in instead.",
        )
    draft = normalize(ld, final_url)
    if not draft["name"] or not (draft["ingredients"] or draft["instructions"]):
        raise RecipeImportError(
            "no_recipe",
            "That page's recipe was missing its ingredients and steps. You can type it in instead.",
        )
    return draft
