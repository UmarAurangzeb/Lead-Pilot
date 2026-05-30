"""
Builds personalised outreach HTML emails with inline portfolio screenshots.

Each email features:
- Niche-matched portfolio project (Next Clean / MyMashwara / GRCify / C2BM)
- 1-2 base64-encoded inline screenshots
- All 4 portfolio links in footer (shows breadth)
- Personalised subject + opening line via LLM
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path

from llm import call_llm

log = logging.getLogger(__name__)

_ASSETS = Path(__file__).resolve().parent.parent / "assets" / "screenshots"

_ALL_LINKS = """
<table style="border-collapse:collapse;width:100%;margin-top:8px">
  <tr>
    <td style="padding:4px 12px 4px 0;font-size:12px;color:#555">
      <a href="https://next-clean.co.uk/" style="color:#1a73e8;text-decoration:none">Next Clean</a> — cleaning marketplace
    </td>
    <td style="padding:4px 12px 4px 0;font-size:12px;color:#555">
      <a href="https://www.mymashwara.com/home" style="color:#1a73e8;text-decoration:none">MyMashwara</a> — healthcare platform
    </td>
  </tr>
  <tr>
    <td style="padding:4px 12px 4px 0;font-size:12px;color:#555">
      <a href="https://grcify.co/" style="color:#1a73e8;text-decoration:none">GRCify</a> — compliance &amp; GRC
    </td>
    <td style="padding:4px 12px 4px 0;font-size:12px;color:#555">
      <a href="https://www.c2bmsolutions.com/" style="color:#1a73e8;text-decoration:none">C2BM Solutions</a> — operations platform
    </td>
  </tr>
</table>
"""


def _load_screenshot(folder: str, filename: str) -> str | None:
    """Return a base64 data URI for the image, or None if not found."""
    path = _ASSETS / folder / filename
    if not path.exists():
        # Try any PNG in the folder as fallback
        folder_path = _ASSETS / folder
        pngs = list(folder_path.glob("*.png")) if folder_path.exists() else []
        if not pngs:
            return None
        path = pngs[0]
    try:
        data = base64.b64encode(path.read_bytes()).decode()
        return f"data:image/png;base64,{data}"
    except Exception:
        return None


def _screenshot_html(folder: str, alt: str) -> str:
    src = _load_screenshot(folder, "homepage.png") or _load_screenshot(folder, "homepage_ss.png")
    if not src:
        return ""
    return (
        f'<img src="{src}" alt="{alt}" '
        f'style="max-width:520px;width:100%;border-radius:6px;border:1px solid #e0e0e0;margin:12px 0">'
    )


def _llm_opening(business_name: str, niche: str, location: str) -> str:
    system = "You are writing a concise, professional cold-outreach email. One sentence only. No fluff."
    user = (
        f"Write a single opening sentence for an email to '{business_name}', "
        f"a {niche} business{' in ' + location if location else ''}. "
        "Mention something specific about why you reached out to them specifically. "
        "Sound human, not salesy. Do not start with 'I'."
    )
    try:
        return call_llm(system, user, temperature=0.7).strip()
    except Exception:
        return f"Came across {business_name} while researching {niche} businesses and wanted to reach out."


def build_email(
    *,
    business_name: str,
    niche: str,
    location: str,
    portfolio: dict,
) -> tuple[str, str]:
    """Return (subject, html_body) for a personalised outreach email."""

    opening = _llm_opening(business_name, niche, location)
    ss_html = _screenshot_html(portfolio["folder"], portfolio["name"])

    subject = f"Quick note — I built something relevant to {business_name}"

    body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Georgia,serif;max-width:600px;margin:0 auto;padding:24px;color:#222;line-height:1.6">

  <p style="margin:0 0 16px">{opening}</p>

  <p style="margin:0 0 16px">
    My name is Umar — I'm a software engineer who specialises in building clean,
    production-ready web products. One recent project I thought you'd find interesting:
  </p>

  <!-- Featured portfolio project -->
  <div style="background:#f8f9fa;border-left:3px solid #1a73e8;padding:16px 20px;border-radius:0 6px 6px 0;margin:0 0 16px">
    <p style="margin:0 0 6px;font-weight:bold;font-size:15px">
      <a href="{portfolio['url']}" style="color:#1a73e8;text-decoration:none">{portfolio['name']}</a>
    </p>
    <p style="margin:0 0 8px;font-size:14px;color:#444">{portfolio['desc']}</p>
    <p style="margin:0;font-size:12px;color:#888">{portfolio['tech']}</p>
  </div>

  {ss_html}

  <p style="margin:16px 0">
    If improving your digital setup — whether that's a new site, a booking system,
    or automating a manual workflow — is anywhere on your radar, I'd love a
    quick 15-minute call to see if I can help.
  </p>

  <p style="margin:0 0 24px">
    Happy to share more examples or answer questions first — just reply to this email.
  </p>

  <hr style="border:none;border-top:1px solid #e0e0e0;margin:20px 0">

  <p style="margin:0 0 4px;font-size:14px;font-weight:bold">Umar Aurangzeb</p>
  <p style="margin:0 0 4px;font-size:13px;color:#555">Software Engineer · Sliding Scale Technologies</p>
  <p style="margin:0 0 12px;font-size:13px;color:#555">FAST NUCES Karachi &nbsp;|&nbsp;
    <a href="https://github.com/UmarAurangzeb" style="color:#1a73e8;text-decoration:none">github.com/UmarAurangzeb</a>
    &nbsp;|&nbsp;
    <a href="https://linkedin.com/in/UmarAurangzeb" style="color:#1a73e8;text-decoration:none">LinkedIn</a>
  </p>

  <p style="margin:0 0 6px;font-size:12px;color:#888">Other projects I've shipped:</p>
  {_ALL_LINKS}

</body>
</html>"""

    return subject, body
