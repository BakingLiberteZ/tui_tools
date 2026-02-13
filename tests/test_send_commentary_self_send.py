from sassy_wallet.messages import send_commentary


def test_get_self_send_warning_uses_defined_pool(monkeypatch) -> None:
    captured = {}

    def _fake_choice(options):
        captured["options"] = options
        return "loop warning"

    monkeypatch.setattr(send_commentary.secrets, "choice", _fake_choice)

    out = send_commentary.get_self_send_warning()

    assert out == "loop warning"
    assert captured["options"] == send_commentary.SELF_SEND_WARNINGS

