# memory.py
from supabase.init import cur, conn

def save_leads(leads):
    for lead in leads:
        cur.execute("""
            INSERT INTO leads (title, address, website, reviews_count, score, lead_hash, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (lead_hash) DO NOTHING
        """, (
            lead["title"],
            lead.get("address"),
            lead.get("website"),
            lead.get("reviewsCount", 0),
            lead.get("score", 0),
            lead["lead_hash"],
            lead.get("status", "NEW")
        ))

    conn.commit()

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