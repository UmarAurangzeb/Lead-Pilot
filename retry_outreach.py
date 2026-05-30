"""
retry_outreach.py — re-send emails to QUALIFIED leads that were never contacted.

Handles two cases:
  1. Lead has emails stored in DB → sends immediately (no re-scrape needed)
  2. Lead has no emails in DB     → re-scrapes website, then sends

Usage:
    source venv/bin/activate && python retry_outreach.py

Optional env flags (same as main run):
    OUTREACH_DRY_RUN=true   → print what would be sent, don't actually send
    NICHE_OVERRIDE=cleaning → override the niche stored per-lead (applies to all)
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_ROOT))


def _rescrape_emails(leads_without_emails: list[dict]) -> list[dict]:
    """Re-run the Playwright email scraper for leads that have no stored emails."""
    if not leads_without_emails:
        return []
    log.info("Re-scraping emails for %d leads …", len(leads_without_emails))
    from helpers import enrich_leads_with_emails
    return enrich_leads_with_emails(leads_without_emails)


def _send_to_lead(lead: dict, niche: str, dry_run: bool) -> str:
    from helpers import normalize_email_list
    from templates import build_email, select_portfolio
    from utils.smtp import send_email
    import memory

    recipients = normalize_email_list(lead.get("emails"))
    title = lead.get("title") or "your business"

    if not recipients:
        return f"skip:no-email:{title}"

    portfolio = select_portfolio(niche)
    address = lead.get("address") or ""
    location = address.split(",")[-1].strip() if address else ""
    primary = recipients[0]
    cc = recipients[1:] if len(recipients) > 1 else None

    subject, html_body = build_email(
        business_name=title,
        niche=niche,
        location=location,
        portfolio=portfolio,
    )

    if dry_run:
        return f"dry-run:{title}:{primary}:template={portfolio['name']}"

    try:
        plain = (
            f"Hi,\n\nI came across {title} and wanted to reach out.\n\n"
            f"I'm Umar, a software engineer. I recently built {portfolio['name']} "
            f"({portfolio['url']}) — {portfolio['desc']}\n\n"
            f"Happy to chat if improving your digital setup is on your radar.\n\n"
            f"Best,\nUmar Aurangzeb\numaraurangzeb03@gmail.com"
        )
        send_email(
            to_addrs=primary,
            subject=subject,
            body=plain,
            html_body=html_body,
            cc=cc,
        )
        memory.update_status(lead["lead_hash"], "CONTACTED")
        return f"sent:{title}:{primary}"
    except Exception as exc:
        return f"error:{title}:{primary}:{exc}"


def main() -> None:
    dry_run = os.getenv("OUTREACH_DRY_RUN", "false").lower() in ("1", "true", "yes")
    niche_override = os.getenv("NICHE_OVERRIDE", "").strip()

    import memory
    leads = memory.get_qualified_leads(limit=500)

    if not leads:
        print("No QUALIFIED leads found in DB.")
        return

    print(f"\n{'DRY RUN — ' if dry_run else ''}Found {len(leads)} QUALIFIED lead(s) to contact.\n")

    # Split by whether emails are already stored
    have_emails    = [l for l in leads if l.get("emails")]
    missing_emails = [l for l in leads if not l.get("emails") and l.get("website")]
    no_website     = [l for l in leads if not l.get("emails") and not l.get("website")]

    print(f"  Emails in DB  : {len(have_emails)}")
    print(f"  Need re-scrape: {len(missing_emails)}")
    print(f"  No website    : {len(no_website)}  (will skip)")
    print()

    # Re-scrape missing emails
    if missing_emails:
        rescraped = _rescrape_emails(missing_emails)
        for original, updated in zip(missing_emails, rescraped):
            original["emails"] = updated.get("emails", [])

    all_actionable = have_emails + missing_emails
    results: list[str] = []

    for lead in all_actionable:
        niche = niche_override or lead.get("niche") or "local businesses"
        entry = _send_to_lead(lead, niche, dry_run)
        results.append(entry)
        status_icon = "✓" if entry.startswith(("sent", "dry-run")) else "✗"
        print(f"  {status_icon}  {entry}")

    sent    = sum(1 for r in results if r.startswith("sent"))
    skipped = sum(1 for r in results if r.startswith("skip"))
    errors  = sum(1 for r in results if r.startswith("error"))

    print(f"\n{'─' * 45}")
    print(f"  Sent    : {sent}")
    print(f"  Skipped : {skipped + len(no_website)}")
    print(f"  Errors  : {errors}")
    print(f"{'─' * 45}\n")


if __name__ == "__main__":
    main()
