from init import cur

# enum = Enum("status", ["NEW", "ENRICHED", "SCORED", "QUALIFIED", "CONTACTED", "RESPONDED", "DEAD"])

cur.execute("""
CREATE TABLE IF NOT EXISTS leads (
    id SERIAL PRIMARY KEY,
    title TEXT,
    address TEXT,
    website TEXT,
    reviews_count INT,
    score FLOAT,
    lead_hash TEXT UNIQUE,
    status TEXT DEFAULT 'NEW'
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS queries (
    id SERIAL PRIMARY KEY,
    query TEXT UNIQUE
);
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS outreach (
    id SERIAL PRIMARY KEY,
    lead_hash TEXT UNIQUE
);
""")

