# Security Policy

## Supported Versions

Security fixes are applied to the `main` branch.

## Reporting a Vulnerability

- Do not open public issues for security vulnerabilities.
- Use GitHub private vulnerability reporting for this repository.
- Include:
  - affected version/commit
  - impact and attack scenario
  - reproduction steps or PoC
  - proposed remediation (if available)

We aim to acknowledge reports within 72 hours and provide remediation guidance as quickly as possible.

## Security Release Checklist

Run these before release:

```bash
uv lock
uv sync --dev
python scripts/check_dependency_policy.py
uv run ruff check . --fix
uv run ruff format .
uv run ty check
uv run bandit -r sassy_wallet -ll -ii
uv run pip-audit -l --ignore-vuln CVE-2024-23342
uv run pytest -q
```

## Local Data Hardening Requirements

- Wallet store and backups must be written with private file permissions (`0600`).
- Wallet/log/backup directories must use private permissions (`0700`).
- Logs must redact blockchain identifiers and secret material.
- RPC endpoints must be validated as `https` and normalized before use.

## CI Security Gates

CI enforces:

- quality/test gates in `python-app.yml`:
  - static analysis (`ruff`, `ty`)
  - test suite pass
- dedicated vulnerability gates in `security-audit.yml`:
  - static analysis (`bandit`, medium/high confidence)
  - dependency audit (`pip-audit`)
  - machine-readable report artifacts (`bandit-report.json`, `pip-audit-report.json`, `dependency-sbom.cdx.json`)

## Tracked Exceptions

- `CVE-2024-23342` (`ecdsa==0.19.1`) is currently ignored in `pip-audit` gates because no fixed release is available.
- This package is pulled transitively by `bip_utils`; remove the exception as soon as an upstream fixed chain is available.
