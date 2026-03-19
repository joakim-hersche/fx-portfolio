# Market Dashboard — Business Plan

## Executive Summary

Market Dashboard is an open-source, real-time stock portfolio tracker targeting European cross-border retail investors. It combines professional-grade analytics (Monte Carlo simulations, risk metrics, correlation analysis) with true multi-currency support and a privacy-first, self-hostable architecture.

**Business model**: Open Core — the full product is free and open-source (AGPL v3) for self-hosting, with a hosted SaaS version offering free, paid subscription, and one-time lifetime tiers. Revenue comes from a mix of Pro subscriptions (8 EUR/month) and Lifetime purchases (149 EUR one-time).

**Target**: 300-800 paying users within 3 years, generating 5,000-50,000 EUR annual revenue as a nights-and-weekends side business.

---

## 1. Market Analysis

### Total Addressable Market

- ~90 million retail investors in Europe (Eurostat/ESMA estimates, growing post-COVID)
- ~15-20 million actively manage multi-market portfolios
- Serviceable Addressable Market (SAM): ~2-3 million who use digital portfolio tools and invest across borders
- Serviceable Obtainable Market (SOM): 3,000-10,000 total users over 3 years, 300-800 paying

### Target Segments

**Primary — European cross-border retail investors:**
- Age 30-55, invests across 2-4 exchanges (e.g., home market + US + UK/Swiss)
- Currently uses a mix of broker apps, spreadsheets, and Yahoo Finance
- Pain point: no single tool handles multi-currency P&L correctly
- Willingness to pay: 5-15 EUR/month

**Secondary — Finance students & early-career:**
- Age 20-28, small portfolio (2-8 positions), learning
- Pain point: want real analytics but can't afford Bloomberg/Koyfin Pro
- Willingness to pay: 0 EUR (free tier users, future conversion pipeline)

### Competitive Landscape

| Tool | Price | Multi-currency | Monte Carlo | Self-host | Weakness exploited |
|------|-------|---------------|-------------|-----------|-------------------|
| Sharesight | 19 USD/mo | Yes | No | No | Expensive, no advanced analytics |
| Portseido | 10 USD/mo | Yes | No | No | No simulation, no self-host |
| Portfolio Visualizer | Free/29 USD | USD only | Basic | No | US-only, poor UI |
| Stock Events | Free/5 USD | Partial | No | No | Mobile-only, shallow analytics |
| Koyfin | 35 USD/mo | Yes | No | No | Overkill complexity, expensive |

### Competitive Positioning

Professional-grade analytics (Monte Carlo, risk, diagnostics) + true multi-currency + privacy/self-host option, at a price point that undercuts Sharesight by 50%+. The combination of these four attributes is unique in the market — competitors offer one or two, never all four.

---

## 2. Pricing & Revenue Model

### Tier Structure

| | Free (self-hosted) | Starter (hosted) | Pro (hosted) | Lifetime (hosted) |
|---|---|---|---|---|
| **Price** | 0 EUR forever | 0 EUR | 8 EUR/month or 79 EUR/year | 149 EUR one-time |
| **Positions** | Unlimited | 10 | Unlimited | Unlimited |
| **Portfolios** | Unlimited | 1 | 5 | 3 |
| **Monte Carlo** | Full | 3 runs/month | Full | Full |
| **Excel export** | Full | No | Full | Full |
| **Risk analytics** | Full | Basic + limited Monte Carlo | Full | Full |
| **Data refresh** | Self-managed | 30 min | 15 min | 15 min |
| **Support** | GitHub issues | GitHub issues | Email, 48h | GitHub issues |

### Pricing Rationale

- 10 positions / 1 portfolio is enough to evaluate the product but insufficient for a real investor
- Starter gets 3 Monte Carlo runs/month — enough to experience the value proposition before paying, not enough for regular use
- Monte Carlo and Excel export are highest-perceived-value features — full gating creates a clear upgrade trigger
- Yearly discount (~17% off) rewards commitment and reduces churn
- 8 EUR/month undercuts Sharesight (19 USD) and Portseido (10 USD) while positioning as a serious product
- **Lifetime tier at 149 EUR** (~19 months of Pro) captures users who prefer one-time purchases. Priced high enough to avoid cannibalizing Pro subscriptions. Scoped down (3 portfolios vs. 5, no email support, no future premium-only features) to preserve Pro value. GitHub-issues-only support keeps burden manageable.

### Revenue Projections — Base Case

| | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Total users | 1,000 | 3,500 | 8,000 |
| New paying users (gross) | 50 | 180 | 350 |
| Churned users (~31%/yr of prior base) | 0 | 16 | 67 |
| Net paying users (end of year) | 50 | 214 | 497 |
| — of which subscribers (~70%) | 35 | 150 | 348 |
| — of which lifetime (~30%) | 15 | 64 | 149 |
| Subscriber MRR (end of year) | ~245 EUR | ~1,050 EUR | ~2,440 EUR |
| Lifetime one-time revenue (annual) | ~2,235 EUR | ~7,300 EUR | ~12,700 EUR |
| **Total annual revenue** | **~5,175 EUR** | **~19,900 EUR** | **~42,000 EUR** |

### Revenue Projections — Pessimistic Case

| | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Total users | 400 | 1,200 | 3,000 |
| Net paying users (end of year, 3%) | 12 | 30 | 75 |
| **Total annual revenue** | **~1,000 EUR** | **~3,500 EUR** | **~9,000 EUR** |

### Assumptions

- Conversion rate: 5% Year 1 (early adopters), growing to ~6% by Year 3
- Payment mix: ~70% choose subscription (monthly or annual), ~30% choose Lifetime
- Blended subscriber ARPU: ~7 EUR/month (mix of monthly at 8 EUR and annual at 6.58 EUR effective)
- Monthly churn on subscribers: ~3% (~31% annual)
- Lifetime users: no churn (they paid once; hosting cost is negligible)
- Pessimistic case uses 3% conversion consistently
- Growth driven by GitHub, finance communities, SEO (SEO treated as long-term bet, not primary driver)
- Paying user counts are net of churn

### Cost Structure (estimated annual)

| Item | Year 1 | Year 3 |
|---|---|---|
| Fly.io hosting | 0-60 EUR | ~600 EUR |
| Domain + Cloudflare | ~20 EUR | ~20 EUR |
| Email service (transactional) | 0 EUR | ~50 EUR |
| Payment processor (Stripe, 2.9%) | ~170 EUR | ~2,200 EUR |
| Paid data API fallback (if yfinance breaks) | 0 EUR | ~360 EUR |
| Founder time | Nights & weekends (unpaid) | Nights & weekends (unpaid) |
| **Total costs** | **~250 EUR** | **~3,230 EUR** |
| **Net profit (base case)** | **~4,925 EUR** | **~38,770 EUR** |
| **Net profit (pessimistic)** | **~750 EUR** | **~5,770 EUR** |

---

## 3. Go-To-Market Strategy

### Phase 1 — Seed (Months 1-3): Developer Community

- Polish the GitHub repo: good README with screenshots, one-click Docker deploy, contribution guide
- Post to r/selfhosted, r/europeanfinance, r/investing, Hacker News (Show HN)
- Goal: 500 GitHub stars, 200 self-hosted users
- Cost: 0 EUR, a few evenings of writing

### Phase 2 — Launch Hosted SaaS (Months 3-6)

- Launch hosted version with Stripe billing
- Write 2-3 SEO articles: "best portfolio tracker for European investors", "multi-currency portfolio tracking", "free Monte Carlo simulation for stocks"
- Post to EU investing communities (r/eupersonalfinance, Bogleheads EU, local finance forums in DE/NL/SE/CH)
- Early-bird pricing: 59 EUR/year (instead of 79) for first 100 users
- Goal: 50 paying users

### Phase 3 — Grow (Months 6-18)

- GitHub stars and community posts continue driving organic traffic
- SEO articles start ranking (long-term bet, not primary driver)
- Add 1-2 buzz features (e.g., crypto portfolio, EU tax-lot reporting)
- Referral program: give a friend 1 month free, get 1 month free
- Approach EU personal finance YouTubers/bloggers — offer free Pro accounts for reviews
- Goal: 300 paying users by month 18

### What NOT to Do

- **Paid ads** — unit economics don't work at 8 EUR/month with a small audience
- **Product Hunt** — don't launch before hosted version is polished; you get one shot
- **Mobile app** — massive effort, low return; web works fine on mobile
- **Enterprise sales** — completely different motion, will drain all available time

---

## 4. Risk Analysis & Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **yfinance breaks or gets rate-limited** | High | Critical | Abstract data layer behind an interface now (before launch). Fallback options: Twelve Data (~30 USD/month for basic), Financial Modeling Prep (~15 USD/month), or Alpha Vantage (free tier + 50 USD/month). At Year 1 revenue, a 30 USD/month API cost is 7% of base-case revenue — manageable. At scale, pass cost via Pro pricing. **Do not wait for yfinance to break; build the abstraction layer before SaaS launch.** |
| **Not enough users find the product** | Medium | High | GitHub and community posts are the primary driver, not SEO. If <100 total users at 6 months, product-market fit isn't there. |
| **Competitor drops price or adds free tier** | Medium | Medium | Sharesight or Portseido launching a 5 USD/month tier or free plan is the most likely competitive threat. Response: lean into self-host + privacy angle (they can't match this) and community/open-source trust. Don't enter a price war. |
| **Someone forks and hosts competing SaaS** | Low | Medium | AGPL requires open-sourcing their version. Brand, community, and iteration speed are the moat. |
| **A competitor adds Monte Carlo** | Medium | Low | Monte Carlo alone isn't the moat — the combination of multi-currency + analytics + privacy + price is. |
| **Hosting costs spike** | Low | Low | Sessions are lightweight (WebSocket + cached data). Fly.io scales cheaply. Only matters at 10,000+ concurrent users. |
| **Regulatory / financial advice liability** | Low | Medium | Clear disclaimers: "not financial advice, informational purposes only." No buy/sell recommendations. |
| **Founder burnout** | Medium | High | Hard cap: max 10 hours/week. If it can't grow within that constraint, the model is wrong. |

### Kill Criteria

Walk away if:
- After 12 months: fewer than 30 paying users despite consistent marketing effort
- yfinance permanently breaks and the cheapest alternative API costs more than revenue
- You stop enjoying it

---

## 5. Key Metrics

Track from day one, review monthly:

| Metric | Why | Year 1 Target |
|---|---|---|
| **GitHub stars** | Leading indicator of awareness | 500 |
| **Weekly active users (hosted)** | Retention signal | 50% of signups return weekly |
| **Free-to-paid conversion rate** | Is the paywall positioned correctly? | 5-8% |
| **Monthly churn (Pro)** | Are paying users staying? | <5% |
| **Monthly recurring revenue (MRR)** | The number that matters | 480 EUR |

Don't build analytics infrastructure for this. A spreadsheet updated monthly is sufficient until 500+ users.

---

## 6. Implementation Prerequisites

Before monetization can begin, the following must be in place:

1. **Multi-tenant architecture** — the app currently uses browser localStorage via NiceGUI's `app.storage.user`. A hosted SaaS serving thousands of users needs proper database-backed storage, user data isolation, session management, and security boundaries. This is a significant architectural change, not a minor engineering task.
2. **User authentication** — email/password or OAuth for multi-device access and account recovery
3. **Stripe integration** — billing, subscription management, webhooks for both recurring and one-time payments
4. **Feature gating** — tier-based access control for position limits, Monte Carlo runs, export
5. **Data layer abstraction** — decouple from yfinance to enable fallback APIs. Build this before SaaS launch, not after yfinance breaks.
6. **GDPR compliance** — privacy policy, terms of service, data processing documentation, right to deletion, data export (Art. 20 portability), and a plan for what happens to user data if the project shuts down. Required for any EU-targeting product that processes financial data.
7. **Disclaimers** — "not financial advice" on every page with analytics
8. **Onboarding flow** — first-time user experience for non-technical hosted users

These are engineering tasks that should be planned and prioritized separately from the business plan.
