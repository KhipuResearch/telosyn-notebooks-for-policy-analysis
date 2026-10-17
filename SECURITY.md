<!--
© 2026 Deloatch, Williams, Faison & Parker, LLLP. All rights reserved.
Property of Deloatch, Williams, Faison & Parker, LLLP; exclusively licensed to Telosyn, Inc.
SPDX-License-Identifier: LicenseRef-Proprietary
-->

# Security Policy

## Reporting a vulnerability

**Do not report security problems through public GitHub issues.**

Email **contact@telosyn.co** with: what the problem is, the file or notebook it
affects (path and, if relevant, commit), how to reproduce it, and what you
believe the impact to be. You will receive an acknowledgment, and the report
will be worked with you until it is resolved. Public disclosure follows a fix,
and you will be credited unless you ask not to be.

## What the repository does to protect you

**Credentials.** The notebooks read at most six named API keys, all free, from
a file you keep outside the repository and point to with `KRL_SECRETS_PATH`:

```bash
mkdir -p ~/.config/telosyn-notebooks
cp .env.example ~/.config/telosyn-notebooks/keys.env       # fill in your keys
export KRL_SECRETS_PATH=~/.config/telosyn-notebooks/keys.env
```

The six names are a closed set (`ALLOWED_KEYS` in
`src/krl_tutorials_data/sources.py`). Anything else in that file is never
opened. Keys are never logged, echoed or written into a notebook's output; one
release gate scans committed output for key material, and the client redacts
credentials from any error it surfaces. A filled-in `.env` is ignored by git,
and `.gitleaks.toml` and the pre-commit configuration scan for secrets before a
commit lands.

**Data.** The notebooks retrieve only public, published data from the sources
named in each provenance record. No personal data is collected or stored.

**Dependencies.** Runtime dependencies are declared in `pyproject.toml` and
checked by a test that every one is actually imported and nothing imported is
undeclared. Dependabot is enabled.

**Network.** The test suite makes no network calls. Only a notebook, run by you
with your keys, reaches a publisher's endpoint, and every such retrieval is
recorded with its digest.

## Scope

This policy covers the contents of this repository. Problems with a publisher's
API belong with that publisher.
