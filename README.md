# 🥖 Sassy Wallet

**A Tezos TUI wallet with opinions, jokes, and real controls.**

## What it is

A terminal wallet that **doesn’t hide the knobs**. You learn Tezos by doing Tezos.

## Features (current)

- **Import wallets**: secret key, 12/24-word mnemonic, watch-only, backup file
- **Bulk backup / restore** with passphrase encryption (AES-256-GCM + scrypt)
- **Send XTZ** with fee/gas controls and sane warnings
- **Receive** with quick copy and multi-wallet selector
- **Delegate / Stake / Unstake** with dedicated flows (Stake HQ)
- **Wallet status + history** with bakers, staking, and delegation info
- **RPC + network switching** with friendly status feedback
- **Sassy commentary** that keeps you humble ¬_¬

## Install

```bash
pip install -r requirements.txt
python -m sassy_wallet
```

## V2 ideas (wishlist)

- Hardware wallet support
- Smarter tx indexing + cleaner history UX
- Bulk operations (send/undelegate/stake)
- Safer key handling UX + recovery helpers
- UI themes + custom keybindings

## Why this exists

Most wallets treat you like a baby. This one treats you like a grown-up baker.

## Warning (read me, chef)

This is in active development. You *will* find a few surprise croissants (bugs) on the way.  
Use with caution and don’t import your main wallet with the grandpa portfolio in it.

I’m building this because Tezos needs fun, educational TUI tools that **didn’t exist before**.

If this helps, donations fuel more pizzas (features) and V2 work.  
Tezos: `tz1LJmf4GUTrNsZVWXomSfqyWEWdNPo75Wz3`  
A donation button is coming to the landing page.

## License

MIT. Don’t blame the oven if you burn the bread.
