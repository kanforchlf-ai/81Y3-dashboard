#!/usr/bin/env python3
"""
patch_theme.py
Batch-patches all 36 HTML files in 81Y3-dashboard to support light/dark theming.

Changes per file:
  1. <html ...> → <html ... data-theme="dark">
  2. Insert anti-flash JS snippet at the very start of <head>
     (reads localStorage before first paint → zero flicker)
  3. Append <link rel="stylesheet" href="...theme.css"> at end of <head>

Run from the dashboard root:
  python patch_theme.py
"""

import os
import re
import pathlib

ROOT = pathlib.Path(__file__).parent

# ── Anti-flash snippet (inline, <10 lines) ───────────────────────────────────
ANTI_FLASH_JS = """\
<script>
(function(){var t=localStorage.getItem('theme_81y3');if(t==='light'){document.documentElement.setAttribute('data-theme','light');}})();
</script>"""

def depth_prefix(html_path: pathlib.Path) -> str:
    """Return '../' repeated by the nesting depth relative to ROOT."""
    rel = html_path.parent.relative_to(ROOT)
    depth = len(rel.parts)
    return "../" * depth

def patch_file(html_path: pathlib.Path):
    text = html_path.read_text(encoding="utf-8")
    original = text
    changed = False

    # ── 1. Add data-theme="dark" to <html> ──────────────────────────────────
    # Match <html ...> but only if data-theme not already present
    if 'data-theme=' not in text:
        text = re.sub(
            r'<html\b([^>]*)>',
            lambda m: f'<html{m.group(1)} data-theme="dark">',
            text, count=1
        )
        changed = True

    # ── 2. Insert anti-flash JS right after <head> ───────────────────────────
    if 'localStorage.getItem(\'theme_81y3\')' not in text:
        text = re.sub(
            r'(<head[^>]*>)',
            lambda m: m.group(1) + "\n" + ANTI_FLASH_JS,
            text, count=1
        )
        changed = True

    # ── 3. Append theme.css link before </head> ─────────────────────────────
    prefix = depth_prefix(html_path)
    css_href = f"{prefix}theme.css"
    link_tag = f'<link rel="stylesheet" href="{css_href}">'

    if 'theme.css' not in text:
        text = re.sub(
            r'(</head>)',
            f'{link_tag}\n\\1',
            text, count=1
        )
        changed = True

    if changed:
        html_path.write_text(text, encoding="utf-8")
        print(f"  patched  {html_path.relative_to(ROOT)}")
    else:
        print(f"  skipped  {html_path.relative_to(ROOT)}  (already done)")

def main():
    html_files = list(ROOT.rglob("*.html"))
    # Exclude any backup / temp files
    html_files = [p for p in html_files if ".bak" not in p.name]
    print(f"Found {len(html_files)} HTML files\n")
    for f in sorted(html_files):
        patch_file(f)
    print(f"\nDone. {len(html_files)} files processed.")

if __name__ == "__main__":
    main()
