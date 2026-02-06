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
- Follow-up issue record for removing the temporary ignore: `SECURITY_FOLLOWUPS.md` (`SF-2026-02-06-001`).

## CI/CD Hardening Implemented

- `python-app.yml`:
- Lock-first flow (`uv lock`, `uv sync --dev --frozen`).
- Dependency policy gate added.
- Quality gates: `ruff`, `ty` (full `ty check` scope), tests.

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
- Stake flow worker isolation + overlapping submit guard regressions.

## Current Validation Baseline

- `uv run ruff check .`: passing.
- `pytest -q`: passing (`78 passed, 1 skipped` in latest run).
- `bandit -r sassy_wallet -ll -ii`: clean.
- `scripts/check_dependency_policy.py`: passing.
- `pip-audit -l`: reports only `ecdsa==0.19.1` (`CVE-2024-23342`) pending upstream fix.
- `ty` installed (`0.0.15`) and active.
- `ty check sassy_wallet`: **All checks passed**.
- `ty check` full repo: **All checks passed** after test harness typing cleanup and ty analysis config updates.

## Type-Checking Hardening (2026-02-06)

- Closed remaining `ty` errors in message modules:
- `sassy_wallet/messages/bakery.py`
- `sassy_wallet/messages/staking.py`
- Removed stale `type: ignore` suppressions and tightened signatures:
- `sassy_wallet/core/logger.py`
- `sassy_wallet/core/store.py`
- Hardened UI typing/null-safety in high-risk flows:
- explicit `WalletApp` casts for threaded UI callbacks (`_ui`) in estimate/load/delegate/stake/unstake/send flows.
- captured `selected_account`/`selected_name` before async modal factories to avoid optional-attribute races.
- removed redundant `type: ignore[attr-defined]` from `push_screen_wait` call sites.
- Additional debt reduction outside prod module scope:
- `scripts/smoke_textual_pilot.py` now uses explicit `Any` casts for intentional monkeypatching and valid fixture account types (`enc=None`), bringing that script to `ty`-clean.
- `scripts/check_dependency_policy.py` cleanup removed stale unused type-ignore on `tomllib` fallback assignment.
- Test harness typing cleanup:
- `tests/test_ui_pending_history_scope.py`
- `tests/test_stake_flow_integration.py`
- `tests/test_history_selection_guards.py`
- `tests/test_history_title.py`
- `tests/test_backup_import_security.py`
- `tests/test_rpc_fallback_security.py`
- `tests/test_delegate_fill_params.py`
- `tests/test_send_overrides.py`
- `tests/test_stake_selector_layout.py`
- `tests/test_stake_status_infer.py`
- Added `ty` analysis allowance for environment/tooling imports in `pyproject.toml` (`pytest`, `setuptools`) to avoid false negatives from runner-specific module discovery.

## History Reliability Hardening (2026-02-06)

- Deep review focused on disappearing/misclassified rows after rapid `stake` + `change_baker` sequences.
- `get_xtz_history` now uses semantic dedupe (same hash + same semantic signature) instead of dropping everything by hash.
- Shared-hash delegation preference is now limited to likely duplicate artifacts (zero-amount staking rows), so non-zero `stake/unstake` rows are preserved.
- Added and updated regression tests for:
- shared-hash delegation/staking precedence
- preserving non-zero staking rows on shared hashes
- pending merge + shadow behavior
- hash-resolution fallback to staking endpoint
- Added runtime debug export for field QA:
- `Ctrl+D` in app exports `logs/history_debug_*.json` with visible history, cache, pending ops, overrides, and live pull.

## Stake Flow Reliability Notes (2026-02-06)

- Fixed a stake-flow reliability regression where the stake modal could be left without an active owner worker and the payload was not dispatched.
- `WalletApp.action_stake()` now starts `_run_stake_flow` in a dedicated worker group (`stake-flow`) to avoid cancellation collisions with unrelated exclusive workers.
- `StakeScreen.stake_pressed()` now has an in-screen reentry guard to prevent overlapping submits from event/key bounce while confirmation is still in progress.

## Change Baker/Staking Semantics Hardening (2026-02-06)

- Audited against Tezos docs and aligned UX with protocol semantics:
- Changing baker is a `delegation` operation.
- If wallet has staked tez, changing delegate transitions that stake into unstaking/frozen state and it must finalize before new stake with the new delegate.

- Implementation updates:
- Chain-state snapshots now carry `unstaked_mutez` (RPC + TzKT paths).
- Stake UI now surfaces pending-unstake state and blocks stake submit when unstake-from-baker-change is still pending.
- Change-baker confirm/status copy now explicitly warns about implicit unstake/finalization delay.
- Wallet-info cache grace fallback no longer preserves stale staked balance when unstaked balance is present.

- Added regression coverage:
- `tests/test_stake_flow_integration.py::test_stake_flow_blocks_when_pending_unstake_exists_after_baker_change`
- `tests/test_stake_status_infer.py::test_get_wallet_chain_state_marks_staking_active_when_unstaked_balance_present` now asserts `unstaked_mutez`.

## Manual QA Playbook (2026-02-06)

- Added guided checklist for interactive validation:
- `QA_CHANGE_BAKER.md`
- `QA_HISTORY_RELIABILITY.md`
- Covers:
- change baker with/without active stake
- immediate post-change stake lock expectations
- same-baker no-op guard
- cancel/back safety
- copy consistency checks in encryption password modals
- history row retention across mixed `change_baker`/`stake`/`unstake`/`send` sequences
- debug capture path with `Ctrl+D` snapshot export

## Copy Consistency (Encryption Password)

- User-visible messages in `Enter Your Encryption Password` modals were normalized:
- `Wrong passphrase` -> `Wrong encryption password`
- `Never share this passphrase` -> `Never share this encryption password`
- Staking cancel reason now references `encryption password` instead of `passphrase`.

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
