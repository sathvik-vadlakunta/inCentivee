"""Re-register the blog template script on a customer's Webflow site.

Usage: python scripts/update_blog_template.py [customer_id]
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from geo_agent.db import CustomerDB
from geo_agent.publishers.webflow import WebflowPublisher
from geo_agent.publishers.webflow_content import WebflowContentPublisher

customer_id = sys.argv[1] if len(sys.argv) > 1 else "smileshape"
db_path = os.environ.get("DB_PATH", "data/practicerank.db")

db = CustomerDB(db_path)
customer = db.get_customer(customer_id)
if not customer:
    print(f"Customer '{customer_id}' not found")
    sys.exit(1)

oauth_token = db.get_webflow_oauth_token(customer_id)
if not oauth_token:
    print(f"No Webflow OAuth token for '{customer_id}'")
    sys.exit(1)

site_id = customer.get("webflow_site_id", "")
if not site_id:
    print(f"No webflow_site_id for '{customer_id}'")
    sys.exit(1)

print(f"Customer: {customer['name']} (site_id={site_id})")

publisher = WebflowPublisher(api_key=oauth_token, site_id=site_id)
content_pub = WebflowContentPublisher(publisher, db, customer_id)

print("Setting up blog CMS template...")
ok = content_pub.setup_cms_template("blog_posts")
if ok:
    print("Blog template registered and applied successfully!")
    print("Publishing site...")
    published = publisher.publish_site()
    print("Site published!" if published else "Failed to publish site")
else:
    print("Failed to setup blog template")

publisher.close()
db.close()
