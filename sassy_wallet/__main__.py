"""Entry point for Sassy Wallet CLI application."""

from sassy_wallet.ui.app import WalletApp, setup_logging


def main():
    """Main entry point for the application."""
    setup_logging()
    app = WalletApp()
    app.run()


if __name__ == "__main__":
    main()
