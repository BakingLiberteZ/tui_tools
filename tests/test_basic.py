"""Basic tests for Sassy Wallet."""

import pytest
from sassy_wallet import __version__


def test_version():
    """Test that version is defined."""
    assert __version__ == "1.3.0"


def test_import_core_modules():
    """Test that core modules can be imported."""
    from sassy_wallet.core import crypto, logger, store, tezos
    assert crypto is not None
    assert logger is not None
    assert store is not None
    assert tezos is not None


def test_import_message_modules():
    """Test that message modules can be imported."""
    from sassy_wallet.messages import bakery, balance, staking, empty_wallet, modal
    assert bakery is not None
    assert balance is not None
    assert staking is not None
    assert empty_wallet is not None
    assert modal is not None
