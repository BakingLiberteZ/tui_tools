# Project Memory (Updated 2026-02-06)

## Core Rules

- Use `uv` for all Python workflow.
- Do not use plain `pip`; use `uv` commands.
- Lint/format with `ruff`.
- Type-check with `ty`.

## Environment Notes

- On this machine, `uv` was installed via snap (`astral-uv`).
- If `uv` is not in `PATH`, use `/snap/bin/uv`.
- Main lockfile is committed: `uv.lock`.

## Security Hardening Implemented

- RPC/URL hardening:
- Enforced HTTPS URL normalization and rejection of unsafe schemes.
- Applied validation in core RPC and UI fetch paths.

- Data-at-rest hardening:
- Store/backups/logs now enforce private permissions (`0600` files, `0700` dirs).
- Store writes are atomic and permission-safe.

- Logging hardening:
- Added redaction layer for sensitive blockchain/secret-like data.
- Reduced risky debug output exposure in signing/injection flow.

- Process execution hardening:
- Clipboard subprocess path constrained and hardened (`timeout`, fixed argv allowlist, safe env handling, no shell).

- Bandit noise reduction with explicit rationale:
- Real false positives annotated minimally (`pytezos.using(shell=...)`, BIP39 empty passphrase default).
- Non-security random UI/message calls migrated to `secrets.choice`.

- Backup import hardening:
- Added max file size and max decrypted payload bounds.
- Added malformed payload guards for wallet entries and encrypted blobs.
- Sanitized imported recent destination maps/lists and bounded account import count.

## Dependency/CVE Hardening Implemented

- Runtime deps pinned exactly in `pyproject.toml` and `requirements.txt`.
- Added dependency policy gate script: `scripts/check_dependency_policy.py`.
- Policy enforces:
- Runtime deps must be `==` pinned.
- URL/VCS/path direct deps are rejected.
- `pyproject.toml` runtime deps must match `requirements.txt`.

- Security-sensitive upgrades applied:
- `urllib3` `2.5.0` -> `2.6.0`
- `textual` `7.3.0` -> `7.5.0`
- `cryptography` `46.0.3` -> `46.0.4`
- `bip_utils` aligned at `2.10.0` for resolver compatibility with `pytezos==3.17.0`.
- Additional CVE response:
- `urllib3` further upgraded to `2.6.3` after local `pip-audit` reported `CVE-2026-21441` affecting `2.6.0`.
- `ecdsa` (`CVE-2024-23342`) currently has no fixed version in resolver output; exception is explicitly tracked and temporarily ignored in CI `pip-audit` gates.

## CI/CD Hardening Implemented

- `python-app.yml`:
- Lock-first flow (`uv lock`, `uv sync --dev --frozen`).
- Dependency policy gate added.
- Quality gates: `ruff`, `ty`, tests.

- `security-audit.yml`:
- Dedicated security job with lock-first flow.
- Dependency policy gate.
- Bandit + pip-audit gates.
- Artifacts uploaded:
- `bandit-report.json`
- `pip-audit-report.json`
- `dependency-sbom.cdx.json`

- Added `.github/dependabot.yml` for pip + GitHub Actions updates.

## Security Governance Docs

- Added/updated:
- `SECURITY.md`
- `README.md` security/quality command references

## Test Coverage Added/Strengthened

- Added/updated tests for:
- URL/RPC validation hardening.
- Store permissions/atomic writes.
- Logger redaction behavior.
- Backup import security bounds and malformed payload handling.
- RPC fallback safety behavior.
- Send/delegate/stake flow edge cases and regressions.

## Current Validation Baseline

- `pytest -q`: passing (`48 passed, 1 skipped` in latest run).
- `bandit -r sassy_wallet -ll -ii`: clean.
- `scripts/check_dependency_policy.py`: passing.
- `pip-audit` full online query depends on network availability; enforced in CI `security-audit.yml`.

## Key Commits (Recent)

- `d6c50e4` Harden security posture, pin deps, and add lock-based CI gates
- `739b82d` Upgrade security-sensitive dependencies and refresh lockfile

## Standard Commands

```bash
# Setup
uv venv
uv lock
uv sync --extra dev --frozen

# Policy + quality + security checks
python scripts/check_dependency_policy.py
uv run ruff check . --fix
uv run ruff format .
uv run ty check
uv run bandit -r sassy_wallet -ll -ii
uv run pip-audit -l
uv run pytest -q

# Run app
uv run python -m sassy_wallet
```

## Remaining Next Steps

- Enable branch protection requiring `python-app` and `security-audit`.
- Enable GitHub security features available in the repo plan (CodeQL/secret scanning/push protection).
- Optionally enforce a CI gate that fails if `uv.lock` is missing or stale versus `pyproject.toml`.
