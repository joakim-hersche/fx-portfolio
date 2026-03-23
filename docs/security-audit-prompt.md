# Security Audit Prompt for Claude Code

> Comprehensive security and best-practices audit for a website with accounts, paywall, and open source code.

---

## How to Use

Paste the prompt below into Claude Code at the root of your project. Optionally prepend your stack details to skip auto-detection, e.g.:

```
Tech stack: Node.js, Express, PostgreSQL, Prisma, Stripe, JWT
```

---

## Prompt

```
You are performing a comprehensive application security and best-practices audit. Before doing anything else, map the full project structure and identify the tech stack, framework, ORM, and auth library. State your assumptions before proceeding.

Treat this as an exhaustive audit — do not stop at the first finding per category. Check every file recursively.

---

## Scope
- Audit all files from the project root recursively
- Prioritize: routes/, controllers/, models/, middleware/, auth/, api/, utils/, config/, jobs/, webhooks/
- Ignore: node_modules/, .git/, dist/, build/, coverage/

---

## Security & Best Practice Categories

### 1. SQL Injection & Input Validation
- Raw string concatenation in SQL queries instead of parameterized queries or prepared statements
- Validation only on the client side — no server-side type, length, format, or range enforcement
- Inputs rendered to the UI without sanitization (XSS risk)
- Absence of ORM where raw queries are used
- No schema validation library in use (e.g., Zod, Joi, Yup, Pydantic)

### 2. Password Reset Security
- Tokens not generated with a cryptographically secure PRNG (e.g., crypto.randomBytes)
- Token expiry missing or set beyond 60 minutes
- Tokens not invalidated after first use (not single-use)
- Raw token stored in DB instead of a hashed version
- No logic to invalidate previous tokens when a new reset is requested
- Token not scoped to a specific user ID

### 3. API Rate Limiting
- No rate limiting on any endpoint
- Sensitive endpoints unprotected: login, registration, password reset, OTP/2FA, email verification, contact forms
- Rate limiting global only — not enforced per user or per IP
- No 429 Too Many Requests response or Retry-After header
- Fixed window algorithm where sliding window is more appropriate
- No rate limiting on webhook ingestion endpoints

### 4. Authentication & Session Security
- Weak password hashing: MD5, SHA1, SHA256 without salt — must use bcrypt, argon2, or scrypt
- Session cookies missing HttpOnly, Secure, or SameSite=Strict flags
- JWTs with no expiry, expiry > 24 hours, or no refresh token rotation
- No account lockout or exponential backoff after repeated failed logins
- HTTP used anywhere authentication data is transmitted
- No CSRF protection on state-changing endpoints
- OAuth tokens stored insecurely or not validated properly
- Missing MFA/2FA option for account holders

### 5. Paywall & Subscription Integrity
- Subscription status checked only on the client side — not enforced server-side on every protected request
- No re-verification of subscription status on sensitive API routes (only checked at login)
- Webhook handlers for payment events (Stripe, Paddle, etc.) not verifying the signature before processing
- No idempotency handling on payment webhook processing (risk of duplicate fulfillment)
- Trial/coupon logic bypassable via direct API calls
- Paywalled content or assets served from publicly guessable URLs without auth checks
- No grace period handling for failed payments — immediate hard cutoff with no retry logic
- Plan downgrade not immediately revoking access to higher-tier features

### 6. Logging & Observability
- No structured logging in place (should use JSON-structured logs, not console.log)
- Sensitive data being logged: passwords, tokens, full credit card numbers, PII
- Authentication events not logged: login success, login failure, password reset requested/completed, MFA events
- Paywall/billing events not logged: subscription created, upgraded, downgraded, cancelled, payment failed
- No correlation IDs or request IDs on logs for traceability
- Errors swallowed silently (empty catch blocks, no error forwarding)
- No log retention policy or log rotation configured
- No alerting configured on critical failures (payment failures, repeated auth failures, 500 errors)
- Stack traces or internal error details exposed to the client in API responses

### 7. Secrets & Configuration Management
- API keys, database credentials, or secrets hardcoded in source files
- .env file committed to version control
- No .gitignore entry for .env, secrets, or key files
- Different environments (dev/staging/prod) sharing the same secrets
- No secret rotation strategy in place
- Private keys or certificates checked into the repo

### 8. Open Source Code Exposure
- Sensitive configuration, internal API endpoints, or infrastructure details visible in the public repo
- Admin routes or internal tooling included in the open source codebase without access controls
- Security-sensitive logic (license validation, paywall enforcement, fraud detection) present in the open source portion where it can be studied and bypassed
- No SECURITY.md or responsible disclosure policy in the repo
- No CONTRIBUTING.md or CODE_OF_CONDUCT.md (trust signals for the open source community)
- License file missing or inconsistent with actual usage intent
- Changelog or commit history exposing past vulnerabilities or credentials
- Docker files or CI/CD configs leaking internal URLs, tokens, or environment structure

### 9. Dependency & Supply Chain Security
- Dependencies with known CVEs (audit package.json, requirements.txt, Gemfile, go.mod, etc.)
- No automated dependency scanning configured (Dependabot, Renovate, Snyk)
- Unpinned dependency versions in production (using ^ or ~ ranges without a lockfile)
- Lockfile not committed to the repo
- Use of abandoned or unmaintained packages (check last publish date)
- No integrity checks on third-party scripts loaded client-side (missing SRI hashes)

### 10. CORS, Headers & Transport Security
- CORS configured with wildcard (*) in production
- Missing security headers: Content-Security-Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- HSTS not configured or max-age too short (< 1 year)
- HTTP traffic not redirected to HTTPS
- Cookies transmitted over HTTP
- No certificate pinning on mobile clients if applicable

### 11. File Uploads
- MIME type validated only on the client or via file extension — not server-side via magic bytes
- No file size limit enforced
- Uploaded files stored in a web-accessible directory (should be outside web root or in object storage)
- No malware/virus scanning on uploads
- Filename not sanitized before storage (path traversal risk)
- Direct user-controlled URLs used for file retrieval without signed/expiring URLs

### 12. Error Handling & Resilience
- Unhandled promise rejections or uncaught exceptions that crash the process
- No global error handler middleware
- Error responses inconsistent — some leak internals, some do not
- No graceful shutdown handling (SIGTERM/SIGINT)
- External service calls (payment APIs, email, etc.) with no timeout or retry logic
- No circuit breaker pattern for critical external dependencies

### 13. Admin & Internal Tooling
- Admin routes not behind a separate, strongly authenticated layer
- Admin actions not logged with full actor/action/timestamp audit trail
- No IP allowlisting option for admin access
- Privilege escalation possible via parameter tampering (e.g., passing role=admin in a request body)
- No separation between admin API and user-facing API

### 14. Email Security
- Transactional emails sent without SPF, DKIM, or DMARC records (check configuration or documentation)
- Email enumeration possible via different responses for "email not found" vs "wrong password"
- No rate limiting on email-sending endpoints (abuse vector for spam)
- Unsubscribe or verification links not expiring or not single-use

### 15. Privacy & Data Handling
- PII stored beyond what is necessary (data minimization)
- No data deletion workflow for account closure requests (GDPR/CCPA)
- User data not encrypted at rest for highly sensitive fields
- No privacy policy or terms of service linked from the application
- Analytics or third-party scripts loading without user consent mechanism where required

### 16. Database Security
- Unencrypted database connections or missing TLS requirement
- No prepared statements / parameterized queries for Python (using string concatenation in queries)
- Missing or weak database user permissions (overly privileged database users)
- No database backup strategy or encrypted backups
- Sensitive columns (portfolio values, financial data) not encrypted at rest
- Database query logging enabled in production (exposing sensitive data)
- No database activity monitoring or audit logs for financial transactions

### 17. Cache Security
- Sensitive data cached without expiration (user sessions, paywall status, subscription tokens)
- Cache invalidation logic missing or incomplete
- Shared cache across users or tenants (cache poisoning risk)
- Cache keys predictable or enumerable by attackers
- No cache encryption for distributed caches (Redis, Memcached)
- Session data stored in cache without proper isolation

### 18. Third-Party API Integration & Data Fetching
- External API credentials (stock data providers, FX rates) stored insecurely
- Non-HTTPS calls to external APIs or services
- No validation of data returned from external APIs (injection risk)
- Missing authentication/verification for webhook callbacks from data providers
- No retry logic with exponential backoff for API timeouts
- API rate limits from external providers not respected (risk of IP blocking)
- No fallback or circuit breaker for failed data fetches
- Cached financial data not refreshed at appropriate intervals

### 19. Background Jobs & Async Tasks
- Job queue credentials or connection strings stored insecurely
- Background jobs not logging execution for audit trail
- Failed jobs silently dropped without alerting
- Job data (portfolio calculations, financial metrics) not encrypted in queue
- No idempotency handling for retried financial calculations
- Sensitive data passed in job arguments instead of job ID references
- No timeout on long-running background tasks

### 20. Cryptography & Key Management
- Encryption/decryption using weak algorithms (DES, RC4)
- Hardcoded encryption keys in source code
- Same encryption key used across environments
- No key rotation policy in place
- Random number generation using non-cryptographic generators (random module instead of secrets)
- Encrypted data stored without IV or salt

### 21. Financial Data Security & Compliance
- Portfolio calculations or valuations performed client-side and trusted on server
- No audit trail for financial transactions, portfolio changes, or trade execution
- Foreign exchange rates or stock prices from unverified sources
- No validation that FX rates are recent (stale data risk)
- PII combined with financial data without segregation (joint encryption/access model)
- No protection against concurrent modifications of portfolio (race conditions)
- Financial data transmitted unencrypted or without additional encryption layer
- No compliance audit trail for regulatory requirements (SOX, GDPR, financial regulations)

### 22. Service Worker & Progressive Web App Security
- Service Worker scripts not versioned or integrity-checked
- Service Worker caching stale financial data
- No Content-Security-Policy (CSP) headers restricting Service Worker scope
- Service Worker initialization code open to modification
- Offline mode exposing sensitive financial data without re-authentication
- Service Worker requests not authenticated or validated
- Stale Service Worker updates not forcing user re-authentication for sensitive operations

### 23. API Rate Limiting & Abuse Prevention
- Data export, PDF generation, or report endpoints not rate limited
- WebSocket connections or streaming endpoints not rate limited
- No abuse detection for unusual portfolio activity or bulk data fetches
- Bot detection or CAPTCHA missing on sensitive endpoints
- DDoS protection not implemented (Cloudflare, AWS Shield, etc.)

### 24. Monitoring, Alerting & Incident Response
- No alerting on suspicious activity: failed auth, bulk data access, unusual API usage
- No alerting on payment failures or subscription issues
- No monitoring of external data feed failures (stock/FX provider down)
- No alert for certificate expiry, key rotation due dates
- No incident response plan or runbook for security events
- Critical errors not escalating appropriately

### 25. Mobile & Client-Side Security (if applicable)
- Financial data stored unencrypted in local storage or IndexedDB
- API credentials or tokens stored locally accessible to scripts
- No certificate pinning for API calls to mobile app
- App version checks not forcing security updates
- No timeout for inactive sessions on mobile

### 26. Dependency & Library Version Management
- `requirements.txt` or equivalent lockfile missing or using unpinned versions (e.g., `Flask>=2.0` instead of `Flask==2.3.1`)
- Outdated library versions with known CVEs (check with `pip audit`, `pip-audit`, or Snyk)
- Dependencies not scanned automatically (no CI/CD checks for vulnerable versions)
- No documented dependency update strategy or schedule
- Security patches not being applied promptly for critical vulnerabilities
- Transitive dependencies (dependencies of dependencies) not tracked or audited
- No version pinning for production deployments
- Abandoned or unmaintained libraries still in use (check last update date on PyPI)
- No separate dev/test and production dependency groups (e.g., `requirements-dev.txt`)
- Pinned versions too old (preventing security updates from being applied)
- No automated dependency update tooling (Dependabot, Renovate) configured in CI/CD
- Breaking changes in minor or patch versions causing unexpected failures
- Security advisories from GitHub/PyPI not monitored or acted upon
- Docker base images not regularly updated or scanning for vulnerabilities
- Framework versions (Flask, FastAPI, Django, Streamlit) outdated or end-of-life
- Python version itself outdated or no longer receiving security updates (e.g., Python < 3.8)

---

## Output Format

For each finding produce:
- **Category**
- **Severity**: Critical / High / Medium / Low
- **File path and line number(s)**
- **Description** of the issue
- **Recommended fix** with a concrete code example where applicable

At the end, produce a summary table:

| Category | Issues Found | Critical | High | Medium | Low |
|---|---|---|---|---|---|

If a category has no issues, explicitly state it passed. Do not skip categories.

---

## Execution Instructions
1. Map the full project structure first
2. Identify and state the tech stack before auditing
3. Work through every category methodically and exhaustively
4. Where a fix requires a specific library or service, name it explicitly
5. Flag partial implementations as findings — e.g., rate limiting exists but not on sensitive endpoints
6. Distinguish between issues in open source vs. private portions of the codebase where the split is identifiable
```
