from sassy_wallet.ui.app import StakeScreen


def test_is_same_baker_as_current_true_for_same_address() -> None:
    screen = StakeScreen(accounts=[], rpc="https://rpc.example")
    screen.delegate_addr = "tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb"

    assert screen._is_same_baker_as_current("tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb")
    assert screen._is_same_baker_as_current("  tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb  ")


def test_is_same_baker_as_current_false_for_different_or_missing_address() -> None:
    screen = StakeScreen(accounts=[], rpc="https://rpc.example")
    screen.delegate_addr = "tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb"

    assert not screen._is_same_baker_as_current("tz1aWXP237BLwNHJcCD4b3DutCevhqq2T1Z9")
    assert not screen._is_same_baker_as_current("")

    screen.delegate_addr = None
    assert not screen._is_same_baker_as_current("tz1VSUr8wwNhLAzempoch5d6hLRiTh8Cjcjb")
