from sassy_wallet.core.store import Account
from sassy_wallet.ui.app import StakeScreen


def test_stake_selector_row_places_delegation_status_on_second_line() -> None:
    account = Account(
        name="Test Wallet",
        address="tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb",
        enc=None,
    )
    screen = StakeScreen(accounts=[account], rpc="https://rpc.tzkt.io/mainnet")

    text = screen._format_stake_selector_row(
        account_name=account.name,
        address=account.address,
        balance_mutez=1051000,
        staked_mutez=39998,
        delegate_addr="tz1aSkwEot3L2kmUvcoxzjMomb9mvBNuzFK6",
    )

    top_line, bottom_line = text.split("\n", 1)
    assert "Delegated" not in top_line
    assert "Staked" in top_line
    assert "ꜩ" in top_line
    assert "Delegated" in bottom_line
    assert account.address[:10] in bottom_line


def test_stake_selector_row_shows_not_delegated_on_second_line() -> None:
    account = Account(
        name="Test Wallet",
        address="tz1aSkwEot3L2kmUvcoxzjMomb9mvBNuzFK6",
        enc=None,
    )
    screen = StakeScreen(accounts=[account], rpc="https://rpc.tzkt.io/mainnet")

    text = screen._format_stake_selector_row(
        account_name=account.name,
        address=account.address,
        balance_mutez=50000,
        staked_mutez=0,
        delegate_addr=None,
    )

    top_line, bottom_line = text.split("\n", 1)
    assert "Not Delegated" not in top_line
    assert "Not Delegated" in bottom_line
