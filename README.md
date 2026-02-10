# 💅 Sassy Wallet

**A Tezos TUI wallet with opinions, jokes, and real controls.**

## 🧾 What It Is

A terminal wallet that **doesn’t hide the knobs**. You learn Tezos by doing Tezos.

## ✨ Features (Current)

- 🔐 **Import wallets**: secret key, 12/24-word mnemonic, watch-only, backup file
- 📦 **Bulk backup / restore** with passphrase encryption (AES-256-GCM + scrypt)
- 💸 **Send XTZ** with fee/gas controls and sane warnings
- 📥 **Receive** with quick copy and multi-wallet selector
- 🍞 **Delegate / Change Baker / Stake / Unstake** with dedicated flows (Stake HQ)
- 📊 **Wallet status + history** with baker aliases, staking, and delegation info
- 🔎 **Operation Summary panel** with direct TzKT links per operation
- 🌐 **RPC + network switching** with friendly status feedback
- 😏 **Sassy commentary** that keeps you humble ¬_¬

## 🚀 Install

```bash
uv venv
uv lock
uv sync --dev
uv run python -m sassy_wallet
# or: uv run sassy-wallet
```

## ✅ Quality Checks

```bash
python scripts/check_dependency_policy.py
uv run ruff check . --fix
uv run ruff format .
uv run ty check
uv run bandit -r sassy_wallet -ll -ii
uv run pip-audit -l --ignore-vuln CVE-2024-23342
```

## 🗂️ Data Location

- Store lives at `~/.local/share/sassy-wallet/wallet.json` (XDG on Linux).
- Override with `SASSY_WALLET_STORE_PATH` (full file path) or `SASSY_WALLET_DATA_DIR` (directory).
- Legacy `data/wallet.json` is migrated once and kept as a backup.

## 🛡️ Security

- Security policy and reporting workflow: `SECURITY.md`

## 🧱 Missing Features

- **Unstake Requests** notifications (track and inspect): **pending**

## 🧠 Why This Exists

Most wallets treat you like a baby. This one treats you like a grown-up ADULT.

## ⚠️ Warning (Read Me, Chef)

This is in active development. You *will* find a few surprise croissants (bugs) on the way.  
Use with caution and don’t import your main wallet with the grandpa portfolio in it.

I’m building this because Tezos needs fun, educational TUI tools that **didn’t exist before**.

If this helps, donations fuel more pizzas (features) and V2 work.  
Tezos: `tz1LJmf4GUTrNsZVWXomSfqyWEWdNPo75Wz3`  
A donation button is coming to the landing page.

## 📜 License

MIT. Don’t blame the oven if you burn the bread.
