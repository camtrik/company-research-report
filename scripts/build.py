#!/usr/bin/env python3
"""
build.py — Mirror site/ into site/_dist/ with two transforms:

1. Replace `<!-- include: NAME.html -->` markers with the content of
   `site/partials/NAME.html`.
2. Replace `{{COMPANIES_JSON}}`, `{{BUILD_TIME}}`, and
   `{{SITE_BASE_PATH}}` placeholders.
3. Convert `site/notes/**/*.md` to HTML using notes-template.html.

`site/partials/` and `site/_templates/` are excluded from the output.
Non-HTML files (CSS, JS, JSON, fonts, images) are copied unchanged.

Usage:
    python scripts/build.py
Then:
    python -m http.server 8000 --directory site/_dist
"""
from __future__ import annotations

import json
import os
import re
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DIST = SITE / "_dist"
PARTIALS_DIR = SITE / "partials"
COMPANIES_DIR = SITE / "companies"
NOTES_TEMPLATE = SITE / "_templates" / "notes-template.html"

EXCLUDED_DIR_NAMES = {"partials", "_templates", "_dist"}

INCLUDE_RE = re.compile(r"<!--\s*include:\s*([A-Za-z0-9_.\-]+)\s*-->")
ASSET_RE = re.compile(r'((?:href|src)="[^"]*assets/(?:css|js)/[^"]+\.(?:css|js))"')
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


def normalize_base_path(raw: str | None) -> str:
    if not raw:
        return ""
    path = raw.strip()
    if path in {"", "/"}:
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/")


def process_html(
    text: str,
    partials: dict[str, str],
    companies_json: str,
    build_time: str,
    site_base_path: str,
    cache_bust: str = "",
) -> str:
    def expand(match: re.Match[str]) -> str:
        name = match.group(1)
        return partials.get(name, match.group(0))

    text = INCLUDE_RE.sub(expand, text)
    text = text.replace("{{COMPANIES_JSON}}", companies_json)
    text = text.replace("{{BUILD_TIME}}", build_time)
    text = text.replace("{{SITE_BASE_PATH}}", site_base_path)
    if cache_bust:
        text = ASSET_RE.sub(lambda m: f'{m.group(1)}?v={cache_bust}"', text)
    return text


def build_notes(
    dist: Path,
    template_path: Path,
    partials: dict[str, str],
    companies_json: str,
    build_time: str,
    site_base_path: str,
    cache_bust: str = "",
) -> int:
    try:
        import markdown as md_lib
    except ImportError:
        print("[build] WARNING: 'markdown' package not installed; skipping notes build. Run: pip install markdown")
        return 0

    if not template_path.exists():
        print(f"[build] WARNING: notes template not found at {template_path}")
        return 0

    template = template_path.read_text(encoding="utf-8")
    notes_dist = dist / "notes"
    if not notes_dist.exists():
        return 0

    count = 0
    for md_path in sorted(notes_dist.rglob("*.md")):
        text = md_path.read_text(encoding="utf-8")

        # extract title from first # heading and strip it from content
        title = md_path.parent.name.replace("-", " ").title()
        lines = text.splitlines()
        content_lines: list[str] = []
        title_extracted = False
        for line in lines:
            if not title_extracted and line.startswith("# "):
                title = line[2:].strip()
                title_extracted = True
            else:
                content_lines.append(line)
        # drop leading blank lines after the title
        while content_lines and not content_lines[0].strip():
            content_lines.pop(0)

        md = md_lib.Markdown(
            extensions=["tables", "fenced_code", "toc"],
            extension_configs={"toc": {"toc_depth": "2-3"}},
        )
        content_html = md.convert("\n".join(content_lines))
        toc_html = md.toc  # empty string if no headings

        html = template
        html = html.replace("{{NOTE_TITLE}}", title)
        html = html.replace("{{NOTE_CONTENT}}", content_html)
        html = html.replace("{{NOTE_TOC}}", toc_html)
        html = html.replace("{{NOTE_META}}", "")
        html = process_html(html, partials, companies_json, build_time, site_base_path, cache_bust)

        out_path = md_path.parent / "index.html"
        out_path.write_text(html, encoding="utf-8")
        md_path.unlink()
        count += 1

    return count


def main() -> None:
    if not SITE.exists():
        raise SystemExit(f"site/ not found at {SITE}")

    partials = load_partials()
    companies = collect_companies()
    companies_json = json.dumps(companies, ensure_ascii=False)
    build_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cache_bust = str(int(time.time()))
    site_base_path = normalize_base_path(os.environ.get("SITE_BASE_PATH", ""))

    mirror_site()

    notes_count = build_notes(DIST, NOTES_TEMPLATE, partials, companies_json, build_time, site_base_path, cache_bust)

    html_files = list(DIST.rglob("*.html"))
    for html_path in html_files:
        original = html_path.read_text(encoding="utf-8")
        processed = process_html(original, partials, companies_json, build_time, site_base_path, cache_bust)
        if processed != original:
            html_path.write_text(processed, encoding="utf-8")

    print(f"[build] mirrored to {DIST.relative_to(ROOT)}")
    print(f"[build] partials processed: {len(partials)}")
    print(f"[build] companies indexed: {len(companies)}")
    print(f"[build] notes built: {notes_count}")
    print(f"[build] HTML files transformed: {len(html_files)}")
    print(f"[build] BUILD_TIME = {build_time}")
    print(f"[build] SITE_BASE_PATH = {site_base_path or '/'}")


if __name__ == "__main__":
    main()
