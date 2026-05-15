#!/usr/bin/env python3
"""
build.py — Mirror site/ into site/_dist/ with two transforms:

1. Replace `<!-- include: NAME.html -->` markers with the content of
   `site/partials/NAME.html`.
2. Replace `{{COMPANIES_JSON}}` and `{{BUILD_TIME}}` placeholders.

`site/partials/` and `site/_templates/` are excluded from the output.
Non-HTML files (CSS, JS, JSON, fonts, images) are copied unchanged.

Usage:
    python scripts/build.py
Then:
    python -m http.server 8000 --directory site/_dist
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DIST = SITE / "_dist"
PARTIALS_DIR = SITE / "partials"
COMPANIES_DIR = SITE / "companies"

EXCLUDED_DIR_NAMES = {"partials", "_templates", "_dist"}

INCLUDE_RE = re.compile(r"<!--\s*include:\s*([A-Za-z0-9_.\-]+)\s*-->")
META_TAG_RE = re.compile(r'<meta\s+data-region="meta"([^>]*?)>', re.DOTALL)
ATTR_RE = re.compile(r'data-([a-zA-Z\-]+)="([^"]*)"')


def load_partials() -> dict[str, str]:
    if not PARTIALS_DIR.exists():
        return {}
    return {p.name: p.read_text(encoding="utf-8") for p in PARTIALS_DIR.glob("*.html")}


def _ignore(_dir: str, names: list[str]) -> list[str]:
    return [n for n in names if n == ".DS_Store" or n.startswith(".")]


def mirror_site() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)
    for item in SITE.iterdir():
        if item.name in EXCLUDED_DIR_NAMES or item.name == ".DS_Store" or item.name.startswith("."):
            continue
        target = DIST / item.name
        if item.is_dir():
            shutil.copytree(item, target, ignore=_ignore)
        else:
            shutil.copy2(item, target)


def parse_meta_attrs(html: str) -> dict | None:
    m = META_TAG_RE.search(html)
    if not m:
        return None
    attrs = dict(ATTR_RE.findall(m.group(1)))
    out: dict = {}
    for key, value in attrs.items():
        normalized = key.replace("-", "_")
        if normalized == "tags":
            out["tags"] = [t.strip() for t in value.split(",") if t.strip()]
        else:
            out[normalized] = value
    return out


def collect_companies() -> list[dict]:
    if not COMPANIES_DIR.exists():
        return []
    rows: list[dict] = []
    for company_dir in sorted(COMPANIES_DIR.iterdir()):
        if not company_dir.is_dir():
            continue
        index = company_dir / "index.html"
        if not index.exists():
            continue
        attrs = parse_meta_attrs(index.read_text(encoding="utf-8"))
        if attrs:
            rows.append(attrs)
    return rows


def process_html(text: str, partials: dict[str, str], companies_json: str, build_time: str) -> str:
    def expand(match: re.Match[str]) -> str:
        name = match.group(1)
        return partials.get(name, match.group(0))

    text = INCLUDE_RE.sub(expand, text)
    text = text.replace("{{COMPANIES_JSON}}", companies_json)
    text = text.replace("{{BUILD_TIME}}", build_time)
    return text


def main() -> None:
    if not SITE.exists():
        raise SystemExit(f"site/ not found at {SITE}")

    partials = load_partials()
    companies = collect_companies()
    companies_json = json.dumps(companies, ensure_ascii=False)
    build_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    mirror_site()

    html_files = list(DIST.rglob("*.html"))
    for html_path in html_files:
        original = html_path.read_text(encoding="utf-8")
        processed = process_html(original, partials, companies_json, build_time)
        if processed != original:
            html_path.write_text(processed, encoding="utf-8")

    print(f"[build] mirrored to {DIST.relative_to(ROOT)}")
    print(f"[build] partials processed: {len(partials)}")
    print(f"[build] companies indexed: {len(companies)}")
    print(f"[build] HTML files transformed: {len(html_files)}")
    print(f"[build] BUILD_TIME = {build_time}")


if __name__ == "__main__":
    main()
