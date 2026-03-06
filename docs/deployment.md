# Deployment Guide

## Infrastructure overview

| Component | Provider | Plan | Cost/month |
|-----------|----------|------|-----------|
| Next.js platform | Railway | Hobby | $5 |
| Agent pipeline (FastAPI) | Railway | Hobby | $5 |
| PostgreSQL | Neon | Free | $0 |
| Demo site hosting | Cloudflare Pages + R2 | Free | $0 |
| Email | Resend | Free (3K/mo) | $0 |
| Domain | Cloudflare | - | ~$12/yr |
| **Total** | | | **~$10/mo + domain** |

## Step 1: Database (Neon)

```bash
# 1. Create project at neon.tech (free tier)
# 2. Copy connection string
# 3. Run migrations
cd platform
DATABASE_URL="postgresql://..." npx prisma db push
```

## Step 2: Cloudflare Setup

```bash
# Install Wrangler
npm install -g wrangler
wrangler login

# Create R2 bucket
wrangler r2 bucket create demo-sites

# Deploy Worker
cd cloudflare
# Edit wrangler.toml: update zone_name and pattern to your domain
wrangler deploy

# Configure DNS wildcard
# In Cloudflare dashboard: add CNAME *.demo → your-worker.workers.dev (proxied)
```

## Step 3: Stripe Configuration

```bash
# 1. Create account at stripe.com
# 2. Add BLIK and Przelewy24 payment methods (Settings > Payment Methods)
# 3. Create 3 products and recurring prices in PLN:
#    - Starter: 29 PLN/month
#    - Business: 79 PLN/month
#    - Pro: 129 PLN/month
# 4. Copy price IDs to .env.local

# 5. Configure webhook endpoint:
#    https://yourplatform.pl/api/webhooks/stripe
#    Events: checkout.session.completed, customer.subscription.deleted, invoice.payment_failed

stripe listen --forward-to localhost:3000/api/webhooks/stripe  # for local dev
```

## Step 4: Resend Configuration

```bash
# 1. Sign up at resend.com (free tier: 3K emails/month)
# 2. Add and verify your sending domain (e.g., yourplatform.pl)
# 3. Configure DNS records (Resend provides SPF, DKIM, DMARC values)
# IMPORTANT: Use a separate subdomain for outreach, e.g., mail.yourplatform.pl
#            Keep yourplatform.pl for transactional emails only
# 4. Copy API key to .env.local
```

## Step 5: Deploy Platform (Railway)

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# Create project
railway init

# Deploy Next.js platform
cd platform
railway up --service platform

# Deploy Agent FastAPI
cd ../agents
# Create requirements.txt already present
railway up --service agents

# Set environment variables in Railway dashboard for both services
```

## Step 6: Google Maps API

```bash
# 1. Go to console.cloud.google.com
# 2. Create project, enable "Places API (New)"
# 3. Enable "PageSpeed Insights API" (free, no billing needed)
# 4. Create API key, restrict to:
#    - Places API (New)
#    - Maps JavaScript API (if using map embeds)
# 5. Copy to agents/.env

# Free quotas:
# - Text Search: 5,000 requests/month (returns 20 results each = 100K businesses)
# - Place Details: 5,000 requests/month
# - PageSpeed Insights: 25,000 queries/day
```

## Step 7: First Run

```bash
# 1. Start local development
cd platform && npm run dev     # http://localhost:3000
cd agents && uvicorn api_server:app --reload  # http://localhost:8000

# 2. Discover first batch of businesses
cd crawler
python discover.py --city Warsaw --category restaurant --limit 50 --output test.jsonl

# 3. Import to platform
# Use the /api/leads POST endpoint or build a import script:
cat test.jsonl | while read line; do
  curl -X POST http://localhost:3000/api/leads \
    -H "Content-Type: application/json" \
    -d "$line"
done

# 4. Generate first demo site from admin dashboard
# Go to http://localhost:3000/dashboard/leads
# Click "Generuj" on any lead
```

## Environment Variables Reference

See `platform/.env.example` and `agents/.env.example` for all required variables.

## Monitoring

For production monitoring, add:
- **Sentry** (Next.js + Python) — error tracking, free tier
- **Cloudflare Analytics** — demo site traffic (built-in, free)
- **Railway metrics** — CPU/memory for agent pipeline
- **Resend dashboard** — email delivery rates, bounces
