import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# Load repo-root .env so DATABASE_URL works when cwd is supabase/ or project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

conn = psycopg2.connect(os.environ["DATABASE_URL"])
conn.autocommit = True
cur = conn.cursor()




