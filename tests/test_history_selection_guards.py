from types import SimpleNamespace

from sassy_wallet.ui.app import WalletApp


def test_apply_loaded_history_if_selected_ignores_stale_wallet_result():
    class Dummy:
        pass

    app = Dummy()
    rendered = []
    loaded_addrs = []
    cleared_addrs = []
    status_msgs = []

    app._history_requested_more = False
    app._get_selected = lambda: SimpleNamespace(address="tz1SELECTED")
    app._render_history = lambda items: rendered.append(items)
    app._set_history_loaded_addr = lambda addr: loaded_addrs.append(addr)
    app._clear_account_loading = lambda addr: cleared_addrs.append(addr)
    app._set_status = lambda msg: status_msgs.append(msg)
    app._set_status_styled_locked = lambda msg, style: status_msgs.append((msg, style))

    WalletApp._apply_loaded_history_if_selected(
        app,
        "tz1OTHER",
        [{"hash": "op1"}],
        quiet=True,
    )

    assert rendered == []
    assert loaded_addrs == []
    assert cleared_addrs == ["tz1OTHER"]
    assert status_msgs == []


def test_apply_loaded_history_if_selected_updates_current_wallet():
    class Dummy:
        pass

    app = Dummy()
    rendered = []
    loaded_addrs = []
    cleared_addrs = []
    status_msgs = []

    app._history_requested_more = False
    app._get_selected = lambda: SimpleNamespace(address="tz1SELECTED")
    app._render_history = lambda items: rendered.append(items)
    app._set_history_loaded_addr = lambda addr: loaded_addrs.append(addr)
    app._clear_account_loading = lambda addr: cleared_addrs.append(addr)
    app._set_status = lambda msg: status_msgs.append(msg)
    app._set_status_styled_locked = lambda msg, style: status_msgs.append((msg, style))

    WalletApp._apply_loaded_history_if_selected(
        app,
        "tz1SELECTED",
        [{"hash": "op1"}],
        quiet=True,
    )

    assert rendered and rendered[0][0]["hash"] == "op1"
    assert loaded_addrs == ["tz1SELECTED"]
    assert cleared_addrs == ["tz1SELECTED"]
    assert status_msgs == []


def test_apply_history_load_error_if_selected_ignores_stale_wallet_error():
    class Dummy:
        pass

    app = Dummy()
    rendered = []
    cleared_addrs = []
    status_msgs = []

    app._get_selected = lambda: SimpleNamespace(address="tz1SELECTED")
    app._render_history = lambda items: rendered.append(items)
    app._set_status = lambda msg: status_msgs.append(msg)
    app._clear_account_loading = lambda addr: cleared_addrs.append(addr)

    WalletApp._apply_history_load_error_if_selected(
        app,
        "tz1OTHER",
        "boom",
        quiet=False,
    )

    assert rendered == []
    assert status_msgs == []
    assert cleared_addrs == ["tz1OTHER"]
