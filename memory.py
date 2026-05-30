# memory.py
import json
from supabase.init import cur, conn


def save_leads(leads):
    for lead in leads:
        emails_raw = lead.get("emails") or []
        emails_json = json.dumps(list(emails_raw)) if emails_raw else None

        cur.execute("""
            INSERT INTO leads (title, address, website, reviews_count, score, lead_hash, status, emails, niche)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lead_hash) DO UPDATE SET
                status = EXCLUDED.status,
                score  = EXCLUDED.score,
                emails = COALESCE(EXCLUDED.emails, leads.emails),
                niche  = COALESCE(EXCLUDED.niche,  leads.niche)
        """, (
            lead["title"],
            lead.get("address"),
            lead.get("website"),
            lead.get("reviewsCount", 0),
            lead.get("score", 0),
            lead["lead_hash"],
            lead.get("status", "NEW"),
            emails_json,
            lead.get("niche"),
        ))

    conn.commit()


def get_qualified_leads(limit: int = 200) -> list[dict]:
    """Return QUALIFIED leads that have not yet been contacted."""
    cur.execute("""
        SELECT title, address, website, score, lead_hash, emails, niche
        FROM leads
        WHERE status = 'QUALIFIED'
        ORDER BY score DESC
        LIMIT %s
    """, (limit,))

    rows = cur.fetchall()
    cols = ["title", "address", "website", "score", "lead_hash", "emails", "niche"]
    results = []
    for row in rows:
        d = dict(zip(cols, row))
        # Deserialise stored JSON email list
        if d["emails"]:
            try:
                d["emails"] = json.loads(d["emails"])
            except Exception:
                d["emails"] = [e.strip() for e in d["emails"].split(",") if e.strip()]
        else:
            d["emails"] = []
        results.append(d)
    return results


def get_new_leads(limit=10):
    cur.execute("""
        SELECT * FROM leads
        WHERE status = 'NEW'
        LIMIT %s
    """, (limit,))
    return cur.fetchall()


def update_status(lead_hash, status):
    cur.execute("""
        UPDATE leads
        SET status = %s
        WHERE lead_hash = %s
    """, (status, lead_hash))
    conn.commit()
