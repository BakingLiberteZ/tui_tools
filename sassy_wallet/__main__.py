"""Entry point for Sassy Wallet CLI application."""

import sys
from sassy_wallet.ui.app import WalletApp


def main():
    """Main entry point for the application."""
    app = WalletApp()
    app.run()


if __name__ == "__main__":
    main()
