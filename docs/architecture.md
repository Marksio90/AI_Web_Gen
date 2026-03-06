# Architecture Deep Dive

## System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                 │
│  Google Places API (New)  │  OpenStreetMap Overpass  │  PageSpeed   │
└─────────────┬─────────────┴──────────────┬──────────┴──────────────┘
              │                            │
              ▼                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CRAWLER (Python)                                  │
│  discover.py — discovers, normalizes, pre-filters businesses        │
│  → Saves to businesses.jsonl  →  POST /api/leads (Next.js)         │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AGENT PIPELINE (Python FastAPI)                   │
│                                                                      │
│  1. CrawlerAgent (gpt-4.1-nano)   — normalize & classify            │
│         ↓                                                            │
│  2. SEOAgent (gpt-4.1-mini)       — PageSpeed + website quality     │
│         ↓  [skip if good website]                                    │
│  3. DesignAgent (gpt-4.1-mini)    — template + colors + fonts       │
│         ↓                                                            │
│  4. ContentAgent (gpt-4.1/Groq)   — Polish website copy             │
│         ↓                                                            │
│  5. QCAgent (gpt-4.1)             — review + retry loop (max 3)     │
│         ↓  [approved]                                                │
│  6. EmailAgent (gpt-4.1-mini)     — 3 A/B/C email variants          │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   ▼                   ▼
┌─────────────────┐  ┌──────────────────┐  ┌─────────────────────┐
│  Astro Build    │  │  PostgreSQL CRM   │  │  Resend (email)     │
│  → static HTML  │  │  (lead tracking) │  │  (PKE-compliant)    │
│  → Cloudflare   │  │                  │  │                     │
│    R2 Storage   │  │                  │  │                     │
└────────┬────────┘  └──────────────────┘  └─────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   CLOUDFLARE WORKER                                  │
│  *.demo.yourplatform.pl  →  R2 bucket lookup  →  serve static site  │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow for One Business

1. **Discovery**: Crawler finds "Salon Urody Magda, Kraków" on Google Maps
   - Has no websiteUri → direct lead candidate

2. **Ingestion**: Saved to PostgreSQL `Lead` table, stage=DISCOVERED

3. **Pipeline trigger**: Manual (admin clicks "Generuj") or scheduled batch
   - POST /process to FastAPI agent service

4. **Agent execution** (~30-60 seconds total):
   - CrawlerAgent normalizes phone (+48 prefix), classifies as BEAUTY_SALON
   - SEOAgent confirms: no website → websiteStatus=NONE
   - DesignAgent selects template: `beauty-elegant`, palette: purple/rose
   - ContentAgent generates Polish copy: hero, services, about, testimonials
   - QCAgent reviews → APPROVED (score 84/100)
   - EmailAgent writes 3 email variants targeting `kontakt@salon-magda.pl`

5. **Site build**: Astro builds static HTML with injected content
   - Uploaded to R2: `demo-sites/salon-urody-magda-krakow-a3f2/`

6. **Demo URL**: `https://salon-urody-magda-krakow-a3f2.demo.yourplatform.pl`

7. **Outreach**: Email sent via Resend (variant A, informational framing)
   - Lead updated: stage=OUTREACH_SENT

8. **Conversion**: Business owner clicks demo link, subscribes for 79 PLN/month
   - Stripe checkout → webhook → stage=CONVERTED

## Cost per Lead (estimated)

| Step | Model | Tokens | Cost |
|------|-------|--------|------|
| Crawler | gpt-4.1-nano | 500 in + 200 out | $0.00013 |
| SEO | gpt-4.1-mini | 800 in + 400 out | $0.00096 |
| Design | gpt-4.1-mini | 600 in + 300 out | $0.00072 |
| Content | Groq/Llama4 | 1500 in + 3000 out | $0.00115 |
| QC | gpt-4.1 | 3000 in + 500 out | $0.0100 |
| Email | gpt-4.1-mini | 800 in + 600 out | $0.00288 |
| **Total** | | | **~$0.016** |

With caching (GPT-4.1 75% cache discount on stable system prompts):
- Effective cost: **~$0.008–0.012 per business** at scale

## Template System

Templates follow this naming convention: `{category}-{style}`

Available templates:
- `restaurant-modern`, `restaurant-warm`, `restaurant-elegant`
- `beauty-minimal`, `beauty-elegant`, `beauty-vibrant`
- `dental-clean`, `dental-professional`, `dental-modern`
- `auto-bold`, `auto-industrial`, `auto-modern`
- `law-prestigious`, `law-modern`, `law-minimal`
- `plumber-trusted`, `plumber-modern`
- `fitness-energetic`, `fitness-modern`
- `pharmacy-clean`
- `hotel-luxury`, `hotel-boutique`

All templates share the same Astro components (`Hero`, `Services`, `About`, etc.)
but differ in section ordering, color defaults, and hero variant selection.

## Database Schema Summary

- **Lead**: core record, one per discovered business
- **Activity**: event log (immutable audit trail)
- **Campaign**: outreach batch with A/B/C variants
- **CampaignLead**: junction + tracking (sent/opened/unsubscribed)
- **UnsubscribeToken**: PKE-compliant one-click unsubscribe
- **User/Account/Session**: next-auth v5 admin auth

## PKE Compliance Checklist

- [x] Target only `biuro@`, `kontakt@`, `info@` — never personal emails
- [x] Informational framing — no "buy", "offer", "subscription" in first contact
- [x] Mandatory footer with sender identity, data source, opt-out link
- [x] One-click unsubscribe (RFC 8058 List-Unsubscribe-Post header)
- [x] Data minimization (business name, address, category — no personal data)
- [x] 30-day retention limit for non-responsive contacts (enforced by stage=LOST)
- [x] DKIM/SPF/DMARC on outreach domain (Resend handles this)
