"""Recipe identity shared by Taste Lab and its offline tools."""

import re


ARCHIVE_ID = re.compile(r"/(\d+)/?$")


def archive_id(row) -> str:
    url = (row["source_url"] or "").split("?")[0].rstrip("/")
    m = ARCHIVE_ID.search(url)
    if m:
        return m.group(1)
    slug = str(row["slug"] or "")
    if slug.isdigit():
        return slug
    return str(row["id"])
