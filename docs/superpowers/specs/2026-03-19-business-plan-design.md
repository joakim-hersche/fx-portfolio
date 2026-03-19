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
- Monte Carlo and Excel export are highest-perceived-value features — gating them creates a clear upgrade trigger
- Yearly discount (~17% off) rewards commitment and reduces churn
- 8 EUR/month undercuts Sharesight (19 USD) and Portseido (10 USD) while positioning as a serious product
- **Lifetime tier at 49 EUR** captures users who would never subscribe but will make a one-time "support the project" purchase — common in open-source (Obsidian, Sublime Text model). Equivalent to ~6 months of Pro; breaks even quickly. Higher conversion rate offsets lower LTV. No email support keeps the support burden manageable.

### Revenue Projections — Base Case

| | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Total users | 1,000 | 4,000 | 12,000 |
| Paying users (5-8%) | 60 | 280 | 800 |
| Monthly revenue | ~480 EUR | ~2,240 EUR | ~6,400 EUR |
| Annual revenue | ~5,760 EUR | ~26,880 EUR | ~76,800 EUR |

### Revenue Projections — Pessimistic Case

| | Year 1 | Year 2 | Year 3 |
|---|---|---|---|
| Total users | 400 | 1,500 | 4,000 |
| Paying users (3-5%) | 15 | 60 | 200 |
| Monthly revenue | ~120 EUR | ~480 EUR | ~1,600 EUR |
| Annual revenue | ~1,440 EUR | ~5,760 EUR | ~19,200 EUR |

### Assumptions

- Conversion rate: 5% Year 1 (early adopters), growing to 7% by Year 3
- Average revenue per user: 8 EUR/month (some on annual discount)
- Monthly churn: ~3% (portfolio trackers are sticky)
- Growth driven by GitHub, finance subreddits, EU investing communities, SEO

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
| **Net profit (base case)** | **~5,500 EUR** | **~73,600 EUR** |
| **Net profit (pessimistic)** | **~1,190 EUR** | **~16,000 EUR** |

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

- SEO compounds from Phase 2 content
- GitHub stars drive organic traffic
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
| **yfinance breaks or gets rate-limited** | High | Critical | Abstract data layer behind an interface. Fallback to paid API (Twelve Data, ~30 USD/month). Pass cost to Pro users if needed. |
| **Not enough users find the product** | Medium | High | Double down on SEO and GitHub presence early. If <100 total users at 6 months, product-market fit isn't there. |
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

1. **Hosted SaaS deployment** — already partially done (Fly.io + Cloudflare)
2. **User authentication** — currently browser-storage only; needs proper auth for multi-device access
3. **Stripe integration** — billing, subscription management, webhooks
4. **Feature gating** — tier-based access control for positions, Monte Carlo, export
5. **Terms of service & privacy policy** — required for payment processing and GDPR compliance
6. **Disclaimers** — "not financial advice" on every page with analytics
7. **Data layer abstraction** — decouple from yfinance to enable fallback APIs
8. **Onboarding flow** — first-time user experience for non-technical hosted users

These are engineering tasks that should be planned and prioritized separately from the business plan.
