from unittest import mock

from mu import __main__


def test_main_calls_run():
    called = {}

    def fake_run():
        called["run"] = True

    with mock.patch("mu.__main__.run", fake_run):
        __main__.main()
    assert called.get("run") is True
