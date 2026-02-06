# Manual QA - Change Baker

Date: 2026-02-06

## Scope

Validate that `Change Baker` behaves as a delegation operation and that stake semantics are correct after switching delegate.

## Preconditions

- App runs in mainnet or ghostnet with a wallet that can sign operations.
- Wallet has at least one outgoing operation history (app policy requirement).
- Optional second wallet for control tests.

## Live Log (optional but recommended)

```bash
tail -f logs/wallet.log | rg --line-buffered "change baker|delegation|stake|unstake|pending|injected|failed"
```

## Test Cases

### TC-01: Change baker when wallet has no active stake

1. Open `Stake Manager`.
2. Select a delegated wallet with `Staked = 0`.
3. Click `Change Baker`.
4. Enter a different valid baker address.
5. Complete encryption password + confirmation flow.

Expected:
- Operation is injected successfully.
- History adds `DEL` entry with `entrypoint=change_baker`.
- New delegate appears after refresh.
- Stake button remains available (no pending unstake lock if staked was zero).

### TC-02: Change baker when wallet has active stake

1. Open `Stake Manager`.
2. Select a delegated wallet with `Staked > 0`.
3. Click `Change Baker`.
4. Enter a different valid baker address.
5. Complete encryption password + confirmation flow.

Expected:
- Operation is injected successfully as delegation.
- Status indicates previous stake moves to unstaking/finalization.
- Wallet info shows pending unstake indicator.
- Stake action is blocked until finalization completes.

### TC-03: Attempt stake immediately after changing baker (with prior stake)

1. Right after TC-02, try to stake any amount.

Expected:
- Flow is blocked before confirm/injection.
- Error/status explains pending unstake must finalize first (~4 cycles).

### TC-04: Same baker guard

1. Open `Change Baker`.
2. Enter current baker address.
3. Confirm.

Expected:
- App does not inject operation.
- Status: already delegated to that baker.

### TC-05: Cancel and back navigation safety

1. Enter `Change Baker` flow.
2. Press `Back` from password modal and from confirmation modal.
3. Press `Cancel`.

Expected:
- No operation is injected.
- UI returns cleanly to Stake Manager without broken focus/state.

### TC-06: Wrong encryption password message coherence

1. In any `Enter Your Encryption Password` modal, type wrong password.

Expected:
- Error says `Wrong encryption password. Try again.`
- No user-visible text in that modal says `passphrase` for this context.

## Pass/Fail Criteria

- Pass when all expected outcomes are met with no unintended operation injection.
- Fail on any mismatch in delegation/stake semantics, stale UI state, or inconsistent copy.
