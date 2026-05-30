"""Maps a niche string to the most relevant portfolio project."""
from __future__ import annotations

NICHE_MAP: dict[str, set[str]] = {
    "cleaning": {"clean", "maid", "domestic", "janitorial", "housekeep", "laundry", "wash", "carpet", "window"},
    "healthcare": {"health", "clinic", "medical", "dental", "doctor", "therapy", "wellness", "physio", "pharmacy", "hospital", "gp", "optician"},
    "compliance": {"compliance", "legal", "finance", "fintech", "regulatory", "audit", "grc", "risk", "insurance", "accounting", "tax"},
    "business": {"hr", "operations", "management", "b2b", "saas", "payroll", "erp", "staffing", "recruitment", "logistics", "dispatch"},
}

PORTFOLIO: dict[str, dict] = {
    "cleaning": {
        "name": "Next Clean",
        "url": "https://next-clean.co.uk/",
        "folder": "next_clean",
        "desc": "A two-sided cleaning marketplace I built with Stripe Connect — customers book, cleaners manage jobs, zero payment disputes post-launch.",
        "tech": "Next.js · Stripe Connect · Supabase",
    },
    "healthcare": {
        "name": "MyMashwara",
        "url": "https://www.mymashwara.com/home",
        "folder": "mymashwara",
        "desc": "Healthcare scheduling platform connecting patients, doctors, and admins with real-time calendar sync and automated conflict detection.",
        "tech": "Next.js · Node.js · Supabase · Prisma",
    },
    "compliance": {
        "name": "GRCify",
        "url": "https://grcify.co/",
        "folder": "grcify",
        "desc": "AI-powered compliance platform with a RAG pipeline over 50+ policy documents — automated policy drafting, scoring, and a compliance chatbot.",
        "tech": "Next.js · FastAPI · RAG · Selenium",
    },
    "business": {
        "name": "C2BM Solutions",
        "url": "https://www.c2bmsolutions.com/",
        "folder": "c2bm",
        "desc": "Internal operations platform — QR-based attendance system, invoice management, and leave tracking serving 200+ employees.",
        "tech": "React · Node.js · PostgreSQL",
    },
}


def select_portfolio(niche: str) -> dict:
    n = niche.lower()
    for category, keywords in NICHE_MAP.items():
        if any(k in n for k in keywords):
            return PORTFOLIO[category]
    return PORTFOLIO["business"]
