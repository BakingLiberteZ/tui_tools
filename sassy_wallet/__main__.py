"""Entry point for Sassy Wallet CLI application."""

import sys
from sassy_wallet.ui.app import TezosWalletApp


def main():
    """Main entry point for the application."""
    app = TezosWalletApp()
    app.run()


if __name__ == "__main__":
    main()
