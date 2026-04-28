# PracticeRank VA Runbook

Step-by-step instructions for managing PracticeRank customers. No technical knowledge required — just follow the steps and run the commands.

## Setup

All commands are run from the project directory:
```
cd ~/dental-marketing
```

Every script has `--help` if you need more options:
```
python scripts/onboard.py --help
```

---

## Adding a New Customer

1. **Run the onboarding script:**
   ```
   python scripts/onboard.py
   ```
   Answer each prompt (practice name, website, contact info). The system will automatically:
   - Detect their website platform (Webflow, Squarespace, WordPress)
   - Look up their Google reviews and rating
   - Find nearby competitors
   - Save everything to the database

2. **Send the onboarding email:**
   - The email is saved at `data/customers/{id}/onboarding-email.txt`
   - Open it, copy the content, and send from Jon's email

3. **Track access grants:**
   As the client grants access to each platform, update the status:
   ```
   python scripts/onboard.py --update-access {customer-id}
   ```
   Follow the prompts to mark each platform as "granted" or "not_needed".

4. **When all access is granted**, the system automatically marks the customer as active.

---

## Monthly Check (Do on the 5th of each month)

1. **Check status of all customers:**
   ```
   python scripts/monthly_status.py
   ```
   This shows:
   - Which customers have staged changes awaiting approval
   - Which have been approved and are ready to publish
   - Which need attention

2. **For pending approvals older than 5 days:**
   Send a follow-up email:
   ```
   python scripts/send_email.py --template 02-access-followup --customer {id} --preview
   ```
   Review the email, then copy and send.

3. **For approved changes:**
   ```
   python -m geo_agent.main --publish --use-db
   ```
   This publishes all approved staged content.

---

## Checking Results

### KPI Report (one customer)
```
python scripts/kpi_report.py --customer {customer-id}
```

### KPI Report (all customers)
```
python scripts/kpi_report.py --all
```

### Track fresh KPIs before reporting
```
python scripts/kpi_report.py --track --customer {customer-id}
```

### Check AI mentions
```
python scripts/check_ai_mentions.py --customer {customer-id} --save
```

### Generate a case study
```
python scripts/generate_case_study.py --customer {customer-id}
```

---

## Importing Legacy Data

If there are customers in `data/customers.json` that need to be imported:
```
python scripts/onboard.py --import-json
```

---

## Common Scenarios

### Client asks "what did you do this month?"
1. Run `python scripts/kpi_report.py --customer {id}`
2. Send the monthly report email:
   ```
   python scripts/send_email.py --template 04-monthly-report --customer {id} --preview
   ```

### New customer but website isn't on Webflow or Squarespace
No problem — the system works with any website. During onboarding, set the platform to `wordpress` or `unknown`. The agent will use the generic crawler to scrape the site.

### Need to re-run the agent for one customer
```
python -m geo_agent.main --customer {id} --use-db --dry-run
```
Remove `--dry-run` to stage changes, or add `--force-publish` to publish immediately.

### Something went wrong with a customer's data
Check the database directly:
```
python -c "from geo_agent.db import CustomerDB; db = CustomerDB(); print(db.get_customer('{id}'))"
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Add customer | `python scripts/onboard.py` |
| Update access | `python scripts/onboard.py --update-access {id}` |
| Monthly status | `python scripts/monthly_status.py` |
| KPI report | `python scripts/kpi_report.py --customer {id}` |
| Preview email | `python scripts/send_email.py --template {name} --customer {id} --preview` |
| Approve changes | `python scripts/approve.py --customer {id}` |
| Publish approved | `python -m geo_agent.main --publish --use-db` |
| AI mentions | `python scripts/check_ai_mentions.py --customer {id} --save` |
| Case study | `python scripts/generate_case_study.py --customer {id}` |
| Import JSON | `python scripts/onboard.py --import-json` |
