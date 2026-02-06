# Security Follow-ups

## SF-2026-02-06-001: Remove temporary pip-audit ignore for `CVE-2024-23342` (`ecdsa`)

- Status: `open`
- Priority: `high`
- Created: `2026-02-06`
- Owner: `maintainers`

### Context

- `pip-audit` reports `CVE-2024-23342` in `ecdsa==0.19.1`.
- `ecdsa` is transitive (currently pulled by `bip_utils`).
- No fixed chain was available when this follow-up was created, so CI currently uses:
  - `--ignore-vuln CVE-2024-23342`

### Required Actions

1. Re-check if a fixed version is available in upstream dependency chain (`bip_utils`/`ecdsa`).
2. Upgrade dependencies and regenerate `uv.lock`.
3. Remove the temporary ignore from `.github/workflows/security-audit.yml`.
4. Run full validation (`pytest`, `bandit`, `pip-audit`) and confirm clean output.
5. Update `SECURITY.md` and `codexmemory.md` to mark this follow-up as resolved.

### Exit Criteria

- `pip-audit -l` passes **without** `--ignore-vuln CVE-2024-23342`.
