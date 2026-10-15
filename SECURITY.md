# Security Policy

## Supported Versions

We provide security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

If you discover a security vulnerability, please send an email to:

**contact@telosyn.co**

Include the following information:

- Type of vulnerability
- Full paths of source file(s) related to the vulnerability
- Location of the affected source code (tag/branch/commit or direct URL)
- Step-by-step instructions to reproduce the issue
- Proof-of-concept or exploit code (if possible)
- Impact of the vulnerability

### What to Expect

- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 5 business days
- **Regular Updates**: Every 5-7 days until resolution
- **Fix Timeline**: Varies by severity (critical issues prioritized)

### Disclosure Policy

- We will confirm receipt of your report
- We will work with you to understand and validate the issue
- We will develop and test a fix
- We will publicly disclose the vulnerability after a fix is released
- We will credit you for the discovery (unless you prefer to remain anonymous)

## Security Best Practices for Users

### API Keys

**Never commit API keys to version control.**

Always use environment variables:

```bash
export FRED_API_KEY=your_key_here
export CENSUS_API_KEY=your_key_here
export BLS_API_KEY=your_key_here
```

Or create a local configuration file (excluded from git):

```bash
# <operator-path>/apikeys
FRED_API_KEY=your_key_here
CENSUS_API_KEY=your_key_here
```

### Data Privacy

- Never include personally identifiable information (PII) in notebooks
- Sanitize or anonymize data before sharing
- Be cautious when publishing notebooks with real data

### Dependencies

Keep dependencies up to date:

```bash
pip install --upgrade -r requirements.txt
```

### Pre-commit Hooks

Use our security checks:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

This runs:
- Secret detection (gitleaks)
- Security scanning (bandit)
- Code quality checks

## Known Issues

We maintain a list of known security issues and their status in our [Security Advisory](https://github.com/the private source repository/security/advisories) page.

## Security Tools

This repository uses:

- **gitleaks**: Secret detection in commits
- **bandit**: Python security linter
- **safety**: Dependency vulnerability scanner
- **pre-commit**: Automated security checks

## Questions?

For security questions (non-vulnerability related), contact:

**contact@telosyn.co**

---

© 2026 Telosyn, Inc. All rights reserved.  
Khipu℠ is a service mark of Telosyn, Inc.
