# AI Local Business Website Generator

A fully automated platform that discovers Polish micro-businesses without professional websites, generates tailored demo sites using AI, and reaches out to business owners — all for under 500 PLN/month.

## Architecture Overview

```
AI_Web_Gen/
├── agents/          # Python multi-agent pipeline (OpenAI Agents SDK)
├── crawler/         # Business discovery (Google Maps + OSM)
├── platform/        # Next.js admin dashboard + mini-CRM
├── templates/       # Astro website templates for demo sites
├── cloudflare/      # Workers reverse proxy for demo hosting
└── docs/            # Technical documentation
```

## Key Features

- **Automated Discovery**: Finds businesses via Google Places API + OpenStreetMap
- **AI Quality Scoring**: PageSpeed Insights + custom scoring pipeline
- **Multi-Agent Generation**: 6 specialized AI agents (GPT-4.1 family + Groq fallback)
- **Template Engine**: 15+ industry-specific Astro templates
- **Outreach System**: PKE-compliant email campaigns via Resend
- **Admin Dashboard**: Full CRM with pipeline management
- **Demo Hosting**: Cloudflare Pages + R2 (unlimited bandwidth, free tier)
- **Payments**: Stripe with BLIK + Przelewy24 support

## Cost Structure (per month)

| Component | Cost |
|-----------|------|
| OpenAI API (2,000 businesses) | ~$60-70 |
| Groq API (bulk generation) | Free tier / ~$5 |
| Google Maps API | Free tier (100K listings) |
| PageSpeed Insights | Free |
| Resend (email) | Free (3K/month) |
| Cloudflare Pages + R2 | Free (1K sites) |
| Vercel/Railway (Next.js) | ~$5-20 |
| PostgreSQL (Neon/Supabase) | Free tier |
| **Total** | **~$70-100 / ~300-430 PLN** |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL database
- API keys: OpenAI, Google Maps, Resend, Stripe

### Setup

```bash
# 1. Agent pipeline
cd agents && pip install -r requirements.txt
cp .env.example .env  # fill in API keys

# 2. Run crawler
cd ../crawler
python discover.py --city Warsaw --category restaurant --limit 1000

# 3. Platform (Next.js)
cd ../platform && npm install
cp .env.example .env.local
npm run dev

# 4. Templates (Astro)
cd ../templates && npm install
npm run dev
```

## Market Opportunity

- **750,000-1,400,000** Polish micro-businesses without professional websites
- Traditional agency cost: **5,000-15,000 PLN** one-time
- Platform subscription: **29-129 PLN/month**
- Estimated conversion: **~10%** from proof-of-value outreach
- Cost per generated website: **~$0.001-0.005** in LLM fees

## Legal Compliance

All outreach is structured to comply with Poland's **PKE (Prawo Komunikacji Elektronicznej)** effective November 10, 2024:
- Targets generic corporate addresses only (biuro@, kontakt@)
- Framed as informational, not commercial
- Includes clear opt-out mechanisms
- Free demo as value delivery, not solicitation