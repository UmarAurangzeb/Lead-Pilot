from __future__ import annotations

import json
import os
import random
import subprocess
from pathlib import Path
from typing import Any

import hashlib

from apify_client import ApifyClient
from dotenv import load_dotenv

from llm import client, DEFAULT_CHAT_MODEL
from prompts import systemPrompts, userPrompts
from schema import QueryResponse
from utils.email_validation import fallback_emails_for_website, mx_filter
_ROOT = Path(__file__).resolve().parent
# Always load repo-root .env (notebook cwd is often notebook/, not LeadPilot/)
load_dotenv(_ROOT / ".env")

_EXTRACT_EMAILS_JS = _ROOT / "extractEmails.js"

def _lead_hash(lead: dict[str, Any]) -> str:
    key = "|".join(
        [
            (lead.get("title") or "").strip().lower(),
            (lead.get("website") or "").strip().lower(),
            (lead.get("address") or "").strip().lower(),
        ]
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


import re as _re

_EMAIL_RE = _re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')
_JUNK_PATTERNS = (
    _re.compile(r'\.(png|jpg|jpeg|gif|svg|webp|ico|pdf|css|js)$', _re.I),
    _re.compile(r'(example|placeholder|youremail|your@email|domain\.com|test@|noreply@no)', _re.I),
    # Cloudflare email-protection beacon address (shows up when decode fails)
    _re.compile(r'email-protection@', _re.I),
    # Sentry / WordPress / Wix / hosting platform noise
    _re.compile(r'@(sentry\.io|wixpress\.com|wordpress\.com|wpengine\.com|squarespace\.com|godaddy\.com|cloudflare\.com)$', _re.I),
)


def normalize_email_list(raw: Any) -> list[str]:
    """Flatten scraped email fields into distinct, validated addresses."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = [raw]
    out = []
    for e in raw:
        if not isinstance(e, str):
            continue
        e = e.strip().lstrip("%20").strip()
        if not _EMAIL_RE.match(e):
            continue
        if any(p.search(e) for p in _JUNK_PATTERNS):
            continue
        out.append(e)
    return list(dict.fromkeys(out))


def complete_query_response(system_prompt: str, user_prompt: str) -> QueryResponse:
    """Structured completion; API + Pydantic enforce QueryResponse (incl. list length)."""
    completion = client.beta.chat.completions.parse(
        model=DEFAULT_CHAT_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format=QueryResponse,
        temperature=0.85,
        top_p=0.9,
        presence_penalty=0.6,
        frequency_penalty=0.4
    )
    parsed = completion.choices[0].message.parsed
    if parsed is None:
        raise ValueError("Structured parse returned no parsed message")
    return parsed

def generate_queries(niche: str, countries: list[str]) -> list[str]:
    variation_seed = random.randint(1, 100000)
    # variation_prompt = f"Generate 5-15 unique search queries to find {niche} businesses in {countries}. Use this seed for variations: {variation_seed}"
    system_prompt = systemPrompts["QueryGenerator"].format(countries=countries)
    user_prompt = userPrompts["QueryGenerator"].format(niche=niche, countries=countries) + f"\n\nVariation seed: {variation_seed}\nGenerate completely different queries from previous runs."
    validated = complete_query_response(system_prompt, user_prompt)
    return validated.queries


apify_client = ApifyClient(os.getenv("APIFY_API_KEY"))


def _normalize_place(item: dict) -> dict:
    return {
        "title": item.get("title"),
        "address": item.get("address"),
        "website": item.get("website"),
        "reviewsCount": int(item.get("reviewsCount") or 0),
        "totalScore": float(item.get("rating") or 0),
        "phone": item.get("phone"),
        "category": item.get("categoryName"),
    }


def fetch_places(queries, max_per_query=20):
    all_results = []

    for query in queries:
        run = apify_client.actor("compass/crawler-google-places").call(
            run_input={
                "searchStringsArray": [query],
                "maxCrawledPlacesPerSearch": max_per_query,
            }
        )
        dataset = apify_client.dataset(run["defaultDatasetId"])

        for item in dataset.iterate_items():
            all_results.append(item)

    return [_normalize_place(item) for item in all_results]


def enrich_leads_with_emails(raw_leads: list[dict]) -> list[dict]:
    """
    Run extractEmails.js (Playwright) on each lead's website; stdin/out JSON.
    Set SCRAPE_EMAILS=false to skip scraping and attach empty emails lists.
    """
    if os.getenv("SCRAPE_EMAILS", "true").lower() in ("0", "false", "no"):
        return [{**lead, "emails": []} for lead in raw_leads]

    proc = subprocess.run(
        ["node", str(_EXTRACT_EMAILS_JS)],
        input=json.dumps(raw_leads).encode("utf-8"),
        capture_output=True,
        cwd=str(_ROOT),
        timeout=int(os.getenv("EMAIL_SCRAPE_TIMEOUT_SEC", "3600")),
        check=False,
    )
    if proc.returncode != 0:
        msg = proc.stderr.decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"extractEmails.js failed (exit {proc.returncode}): {msg}")

    scraped = json.loads(proc.stdout.decode("utf-8"))
    skip_mx = os.getenv("EMAIL_MX_CHECK", "true").lower() in ("0", "false", "no")
    # Pattern fallback is OFF by default — only synthesise info@/contact@ etc.
    # if the user explicitly opts in. Real scraped emails only by default.
    use_fallback = os.getenv("EMAIL_PATTERN_FALLBACK", "false").lower() in ("1", "true", "yes")

    enriched = []
    for lead in scraped:
        emails = normalize_email_list(lead.get("emails"))
        if not skip_mx and emails:
            emails = mx_filter(emails)

        if not emails and use_fallback:
            candidates = fallback_emails_for_website(lead.get("website"))
            emails = normalize_email_list(candidates)

        enriched.append({**lead, "emails": emails})
    return enriched

  