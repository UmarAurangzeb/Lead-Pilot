"""
Screenshot capture — run once before first outreach run.

  python assets/capture_screenshots.py

Does two things:
1. Copies pre-existing screenshots from ~/Desktop/ss/ into assets/screenshots/
2. Launches headless Chromium (Playwright) to capture live pages for
   next_clean and c2bm (which have no ss/ screenshots).
"""
from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCREENSHOTS = HERE / "screenshots"
SS_FOLDER = Path.home() / "Desktop" / "ss"

# ── 1. Pre-existing screenshots to copy from ~/Desktop/ss/ ─────────────────

# macOS screenshot filenames use narrow no-break space ( ) before AM/PM
_NB = " "

SS_COPIES: dict[str, list[tuple[str, str]]] = {
    "mymashwara": [
        (f"Screenshot 2026-02-26 at 1.49.23{_NB}AM.png", "homepage.png"),
        (f"Screenshot 2026-02-01 at 9.59.17{_NB}PM.png", "dashboard.png"),
        (f"Screenshot 2026-02-01 at 5.48.28{_NB}PM.png", "login.png"),
    ],
    "grcify": [
        (f"Screenshot 2026-02-26 at 1.57.29{_NB}AM.png", "homepage.png"),
        (f"Screenshot 2026-02-26 at 1.58.19{_NB}AM.png", "compliance_check.png"),
        (f"Screenshot 2026-02-26 at 2.00.58{_NB}AM.png", "chat.png"),
        (f"Screenshot 2026-02-26 at 2.00.13{_NB}AM.png", "doc_analysis.png"),
    ],
}

# ── 2. Pages to capture live via Playwright ─────────────────────────────────

LIVE_CAPTURES: dict[str, list[tuple[str, str]]] = {
    "next_clean": [
        ("https://next-clean.co.uk/", "homepage.png"),
        ("https://next-clean.co.uk/services", "services.png"),
    ],
    "c2bm": [
        ("https://www.c2bmsolutions.com/", "homepage.png"),
        ("https://www.c2bmsolutions.com/login", "login.png"),
    ],
    # Refresh live shots for mymashwara + grcify too
    "mymashwara": [
        ("https://www.mymashwara.com/home", "homepage_live.png"),
    ],
    "grcify": [
        ("https://grcify.co/", "homepage_live.png"),
    ],
}


def _copy_existing() -> None:
    print("Copying existing screenshots from ~/Desktop/ss/ …")
    for folder, copies in SS_COPIES.items():
        dest_dir = SCREENSHOTS / folder
        dest_dir.mkdir(parents=True, exist_ok=True)
        for src_name, dest_name in copies:
            src = SS_FOLDER / src_name
            dest = dest_dir / dest_name
            if src.exists():
                shutil.copy2(src, dest)
                print(f"  ✓  {folder}/{dest_name}")
            else:
                print(f"  ✗  not found: {src_name}")


def _capture_live() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright Python not available — skipping live captures.")
        print("Install with: pip install playwright && playwright install chromium")
        return

    print("\nCapturing live screenshots via Playwright …")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})

        for folder, pages in LIVE_CAPTURES.items():
            dest_dir = SCREENSHOTS / folder
            dest_dir.mkdir(parents=True, exist_ok=True)
            for url, filename in pages:
                dest = dest_dir / filename
                try:
                    page.goto(url, wait_until="networkidle", timeout=30_000)
                    page.screenshot(path=str(dest), full_page=False)
                    print(f"  ✓  {folder}/{filename}  ←  {url}")
                except Exception as exc:
                    print(f"  ✗  {folder}/{filename}  ({exc})")

        browser.close()


def capture_all() -> None:
    _copy_existing()
    _capture_live()
    print("\nDone. Screenshots in:", SCREENSHOTS)


if __name__ == "__main__":
    capture_all()
