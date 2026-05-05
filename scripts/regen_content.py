"""Regenerate content recommendations for a customer."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from geo_agent.db import CustomerDB
from geo_agent.content_recommender import generate_content_recommendations
from geo_agent.crawler import PageData
import sqlite3

customer_id = sys.argv[1] if len(sys.argv) > 1 else "smileshape"
db_path = os.environ.get("DB_PATH", "data/practicerank.db")

db = CustomerDB(db_path)
customer = db.to_config_customer(customer_id)
if not customer:
    print(f"Customer '{customer_id}' not found")
    sys.exit(1)

print(f"Customer: {customer.name} (type={customer.business_type})")
print(f"Verified quotes: {customer.verified_quotes}")

# Get existing pages from the customer's crawl DB
customer_db_path = f"data/customers/{customer_id}.db"
cdb = sqlite3.connect(customer_db_path)
cdb.row_factory = sqlite3.Row
pages_rows = cdb.execute("SELECT * FROM pages LIMIT 20").fetchall()
pages = []
for r in pages_rows:
    rd = dict(r)
    pages.append(PageData(
        url=rd.get("url", ""),
        title=rd.get("title", ""),
        content=rd.get("content", ""),
        category=rd.get("category", "general") or "general",
        id=rd.get("id", ""),
        slug=rd.get("slug", ""),
        html=rd.get("html", ""),
    ))
print(f"Pages: {len(pages)}")

recs = generate_content_recommendations(customer, pages)
print(f"\nGenerated {len(recs)} recommendations:")
for r in recs:
    has_bq = " [has blockquote]" if "<blockquote" in r.html_snippet.lower() else ""
    print(f"  [{r.rec_type}] {r.title}{has_bq}")

# Save to DB
for r in recs:
    db.conn.execute(
        """INSERT OR REPLACE INTO content_recommendations
        (id, customer_id, rec_type, target_page, title, description, html_snippet, priority, category, status, created_at, ai_impact_reason)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (r.id, r.customer_id, r.rec_type, r.target_page, r.title, r.description,
         r.html_snippet, r.priority, r.category, r.status, r.created_at, r.ai_impact_reason),
    )
db.conn.commit()
print("\nSaved to DB successfully.")
