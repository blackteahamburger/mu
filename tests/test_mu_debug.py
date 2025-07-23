import importlib
import os
import sys
from unittest import mock

import mu.mu_debug as mu_debug


def test_debug_no_filename():
    with mock.patch("sys.stdout") as mock_stdout:
        mu_debug.debug()
        output = mock_stdout.write.call_args_list
        output_str = "".join(call[0][0] for call in output)
        assert (
            "Debugger requires a Python script filename to run." in output_str
        )


def test_debug_with_filename():
    called = {}

    def fake_run(host, port, filepath, args):
        called["host"] = host
        called["port"] = port
        called["filepath"] = filepath
        called["args"] = args

    with (
        mock.patch.object(mu_debug.mu.debugger.runner, "run", fake_run),
        mock.patch.object(mu_debug, "DEBUGGER_PORT", 12345),
    ):
        test_file = "script.py"
        mu_debug.debug(test_file, "arg1", "arg2")
        assert called["host"] == "localhost"
        assert called["port"] == 12345
        assert os.path.basename(called["filepath"]) == "script.py"
        assert called["args"] == ("arg1", "arg2")


def test_win32_pythonw():
    with (
        mock.patch.object(sys, "platform", "win32"),
        mock.patch.object(sys, "executable", r"C:\Python\pythonw.exe"),
        mock.patch.object(sys, "version_info", (3, 9, 0, "final", 0)),
    ):
        py_dir = os.path.dirname(sys.executable)
        version = "{}{}".format(*sys.version_info[:2])
        zip_file = f"python{version}.zip"
        path_to_add = os.path.normcase(os.path.join(py_dir, zip_file))
        with mock.patch("os.path.exists", lambda p: p == path_to_add):
            sys_path_before = list(sys.path)
            importlib.reload(mu_debug)
            assert (
                path_to_add in sys.path
                or path_to_add in sys_path_before + sys.path
            )


def test_main_calls_debug_with_args():
    called = {}

    def fake_debug(*args):
        called["args"] = args

    test_args = ["foo.py", "bar", "baz"]
    with (
        mock.patch.object(mu_debug, "debug", fake_debug),
        mock.patch.object(sys, "argv", ["mu_debug.py"] + test_args),
    ):
        mu_debug.main()
        assert called["args"] == tuple(test_args)
