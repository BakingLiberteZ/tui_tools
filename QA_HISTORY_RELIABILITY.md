# Manual QA - History Reliability

Date: 2026-02-06

## Goal

Validate that history never drops or misclassifies operations after rapid sequences of:

- `change_baker`
- `stake`
- `unstake`
- `send/receive`

## Preconditions

- Use a wallet that can sign operations and has enough XTZ for fees.
- Prefer Ghostnet for repeatability.
- Keep app logs enabled.

## Recommended Live Logs

```bash
tail -f logs/wallet.log | rg --line-buffered "history|pending|change_baker|stake|unstake|resolve|debug"
```

## Debug Snapshot Shortcut

- In app, select wallet and press `Ctrl+D`.
- This exports `logs/history_debug_*.json`.
- Use it whenever UI history looks inconsistent.

## Test Matrix

### HR-01: Change baker only burst

1. Do 3 consecutive `change_baker` operations between two bakers.
2. Refresh app and reopen wallet.

Expected:
- No duplicated same-hash rows.
- Every change appears as `Type=CH`, `Status=BAKER CHANGED`.
- Destination reflects selected baker for each op.

### HR-02: Change baker + stake interleaving

1. `change_baker` A -> B.
2. `stake` small amount.
3. `change_baker` B -> C.
4. Refresh and reopen wallet.

Expected:
- `stake` row remains present.
- No operation disappears after the final baker change.
- Chronological order is stable.

### HR-03: Change baker + unstake

1. Ensure wallet has active stake.
2. `change_baker` to a different baker.
3. `unstake` a small amount.
4. Refresh app.

Expected:
- `unstake` appears as `Type=USTK`, `Status=UNSTAKED`.
- Change-baker rows remain visible.
- No stale previous baker displayed in destination.

### HR-04: Mixed flow with transfer

1. `send` a small transfer.
2. `change_baker`.
3. `stake`.
4. `unstake`.
5. Refresh app.

Expected:
- Transfer row remains (`TX` / `SENT` or `RECEIVED`).
- Stake/unstake rows retain purple coding.
- Delegation/change-baker rows retain yellow coding.

### HR-05: Same-baker guard

1. Open `change_baker`.
2. Enter current baker.

Expected:
- Action button disabled.
- Hint message indicates wallet is already delegating to that baker.
- No RPC/injection is triggered.

## Failure Capture Checklist

If any row is missing/misclassified:

1. Press `Ctrl+D` immediately.
2. Save UTC time and selected wallet address.
3. Record operation hashes shown in status bar or details screen.
4. Attach:
- `logs/history_debug_*.json`
- relevant `logs/wallet.log` segment

## Pass Criteria

- No dropped rows across all test cases.
- Type/status/destination remain semantically correct.
- Behavior is stable after refresh and app restart.
