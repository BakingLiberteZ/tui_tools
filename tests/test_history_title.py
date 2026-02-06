from types import SimpleNamespace
from typing import Any, cast

from sassy_wallet.ui.app import WalletApp


def test_history_title_includes_selected_wallet_name():
    class Dummy:
        pass

    app = cast(Any, Dummy())
    app.history_limit = 10
    app.selected = SimpleNamespace(name="Main Wallet")

    title = WalletApp._history_title_text(app)
    assert "Oven Log" in title
    assert "Main Wallet" in title
    assert "last 10 fresh goodies" in title


def test_history_title_escapes_markup_chars_in_wallet_name():
    class Dummy:
        pass

    app = cast(Any, Dummy())
    app.history_limit = 10
    app.selected = SimpleNamespace(name="A[1] Wallet")

    title = WalletApp._history_title_text(app)
    assert "A\\[1\\] Wallet" in title


def test_history_title_shows_no_wallet_selected_when_none():
    class Dummy:
        pass

    app = cast(Any, Dummy())
    app.history_limit = 10
    app.selected = None

    title = WalletApp._history_title_text(app)
    assert "no wallet selected" in title
