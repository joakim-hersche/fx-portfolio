# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| latest  | :white_check_mark: |

## Reporting a Vulnerability

If you discover a security vulnerability in FX Portfolio, please report it responsibly.

**Do NOT open a public GitHub issue for security vulnerabilities.**

Instead, please email: **security@fxportfolio.app**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgement**: Within 48 hours
- **Initial assessment**: Within 5 business days
- **Fix timeline**: Depends on severity
  - Critical: Patch within 24 hours
  - High: Patch within 7 days
  - Medium: Next scheduled release
  - Low: Backlog

## Scope

The following are in scope for security reports:
- Authentication and session management
- Paywall and subscription bypass
- Data exposure (portfolio data, PII)
- Injection vulnerabilities (SQL, XSS, command injection)
- Rate limiting bypass
- Cryptographic weaknesses

Out of scope:
- Denial of service via excessive requests (use rate limiting)
- Social engineering
- Physical security
- Third-party services (Stripe, yfinance) unless the integration is insecure

## Recognition

We appreciate responsible disclosure and will credit reporters (with permission) in our changelog.
