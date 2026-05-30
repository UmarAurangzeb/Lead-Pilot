#!/usr/bin/env python
"""
LeadPilot — interactive entry point.

Usage:
    source venv/bin/activate && python main.py
    # or: ./venv/bin/python main.py

Prompts for niche and countries, auto-captures portfolio screenshots on first
run, then kicks off the full LangGraph lead-generation workflow.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)

_ROOT = Path(__file__).resolve().parent


def _ensure_screenshots() -> None:
    """Capture portfolio screenshots if they haven't been captured yet."""
    marker = _ROOT / "assets" / "screenshots" / "next_clean" / "homepage.png"
    if marker.exists():
        return
    print("\n[setup] First run — capturing portfolio screenshots …")
    sys.path.insert(0, str(_ROOT))
    from assets.capture_screenshots import capture_all
    capture_all()
    print()


def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"  {label}{suffix}: ").strip()
    return value or default


def _banner() -> None:
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║        LeadPilot — Agentic Lead Gen          ║")
    print("║   A2A · LangGraph · MCP Gmail · Apify        ║")
    print("╚══════════════════════════════════════════════╝")
    print()


def _show_agents() -> None:
    """Print the registered A2A agent cards for visibility."""
    from nodes import _dispatcher
    print("Registered A2A agents:")
    for card in _dispatcher.list_agents():
        skills = ", ".join(s["name"] for s in card["skills"])
        print(f"  • {card['name']}  (v{card['version']})  skills=[{skills}]  endpoint={card['endpoint']}")
    print()


def main() -> None:
    _banner()
    _ensure_screenshots()

    # ── Interactive prompts ──────────────────────────────────────────────────
    print("Configure your lead generation run:\n")
    niche = _prompt("Target niche", "cleaning services")
    raw_countries = _prompt("Target countries (comma-separated)", "UK, US")
    raw_countries = raw_countries.strip().strip("[](){}")
    countries = [c.strip().strip("'\"") for c in raw_countries.split(",") if c.strip()]

    print()
    from templates import select_portfolio
    portfolio = select_portfolio(niche)
    print(f"Portfolio match → '{portfolio['name']}' ({portfolio['url']})")
    print(f"Countries       → {countries}")
    print()

    _show_agents()

    # ── Run graph ────────────────────────────────────────────────────────────
    from graphs import compiled_graph

    thread_id = f"leadpilot-{niche[:20].replace(' ', '-')}"
    print(f"Starting graph  (thread_id={thread_id}) …\n")

    try:
        result = compiled_graph.invoke(
            {"niche": niche, "countries": countries, "iteration": 0},
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:
        print(f"\n[error] Graph execution failed: {exc}")
        raise

    # ── Results ──────────────────────────────────────────────────────────────
    summary = result.get("scoring_summary") or {}
    emails  = result.get("emails") or []
    high    = result.get("high_quality") or []
    rejected = result.get("rejected") or []

    print("\n" + "─" * 50)
    print("RUN COMPLETE")
    print("─" * 50)
    print(f"  Leads scored      : {summary.get('total', len(high) + len(rejected))}")
    print(f"  High quality (≥40): {summary.get('high_quality', len(high))}")
    print(f"  Rejected (<40)    : {summary.get('rejected', len(rejected))}")
    print(f"  Top score         : {summary.get('top_score', '—')}")
    print(f"  Outreach actions  : {len(emails)}")
    print()

    if emails:
        print("Outreach log:")
        for entry in emails:
            print(f"  {entry}")
    else:
        print("No emails sent (check OUTREACH_DRY_RUN / lead quality).")
    print()


if __name__ == "__main__":
    main()
