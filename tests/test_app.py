# -*- coding: utf-8 -*-
"""
Tests for the app script.
"""

import os.path
import subprocess
import sys
from unittest import mock

import pytest

from mu import mu_debug
from mu.app import (
    StartupWorker,
    excepthook,
    is_linux_wayland,
    run,
    setup_exception_handler,
    setup_logging,
)
from mu.debugger.config import DEBUGGER_PORT
from mu.interface.themes import CONTRAST_STYLE, DAY_STYLE, NIGHT_STYLE
from mu.logic import ENCODING, LOG_DIR, LOG_FILE


class DumSig:
    """
    Fake signal for mocking purposes

    Only supports a signal callback
    """

    def __init__(self):
        """
        Setup the signal
        """

        # Setup a fallback handled
        @self.connect
        def default(*args):
            # ... and throw an exception because it still exists
            raise Exception("No signal handler connected")

    def connect(self, func):
        """
        Set the callback function
        """
        self.func = func
        return func

    def emit(self, *args):
        """
        Proxy the callback function
        """
        self.func(*args)


def test_worker_fail():
    """
    Ensure that exceptions encountered during Mu's start-up are handled in the
    expected manner.
    """
    worker = StartupWorker()
    worker.finished = mock.MagicMock()
    worker.failed = mock.MagicMock()
    worker.failed.emit = mock.MagicMock()
    with (
        mock.patch("mu.app.traceback.extract_stack", return_value=["stack"]),
        mock.patch(
            "mu.app.traceback.format_list", return_value=["formatted stack"]
        ),
        mock.patch(
            "mu.app.traceback.format_exc", return_value="formatted exc"
        ),
        mock.patch("mu.app.time.sleep") as sleep,
    ):

        def raise_exc():
            raise Exception("fail!")

        worker.finished.emit = raise_exc
        with pytest.raises(Exception, match="fail!"):
            worker.run()
        worker.failed.emit.assert_called_once()
        sleep.assert_called_once_with(7)


def test_setup_logging_without_envvar():
    """
    Ensure that logging is set up in some way.

    Resetting the MU_LOG_TO_STDOUT env var should mean stdout logging is disabled
    """
    with (
        mock.patch.dict(os.environ, {}, clear=False),
        mock.patch("mu.app.TimedRotatingFileHandler") as log_conf,
        mock.patch("mu.app.os.path.exists", return_value=False),
        mock.patch("mu.app.logging") as logging,
        mock.patch("mu.app.os.makedirs", return_value=None) as mkdir,
    ):
        setup_logging()
        mkdir.assert_called_once_with(LOG_DIR, exist_ok=True)
        log_conf.assert_called_once_with(
            LOG_FILE,
            when="midnight",
            backupCount=5,
            delay=0,
            encoding=ENCODING,
        )
        logging.getLogger.assert_called_once_with()


def test_setup_logging_with_envvar():
    """
    Ensure that logging is set up in some way.

    Setting the MU_LOG_TO_STDOUT env var ensures that stdout logging
    will be enabled
    """
    with (
        mock.patch.dict(os.environ, {"MU_LOG_TO_STDOUT": "1"}, clear=False),
        mock.patch("mu.app.TimedRotatingFileHandler") as log_conf,
        mock.patch("mu.app.os.path.exists", return_value=False),
        mock.patch("mu.app.logging") as logging,
        mock.patch("mu.app.os.makedirs", return_value=None) as mkdir,
    ):
        setup_logging()
        mkdir.assert_called_once_with(LOG_DIR, exist_ok=True)
        log_conf.assert_called_once_with(
            LOG_FILE,
            when="midnight",
            backupCount=5,
            delay=0,
            encoding=ENCODING,
        )
        logging.getLogger.assert_called_once_with()


def test_setup_except_hook():
    """
    confirm that setup_exception_handler() is setting up the global exception hook
    """
    saved = sys.excepthook
    setup_exception_handler()
    assert sys.excepthook == excepthook
    sys.excepthook = saved


def test_run():
    """
    Ensure the run function sets things up in the expected way.

    Why check this?

    We need to know if something fundamental has inadvertently changed and
    these tests highlight such a case.

    Testing the call_count and mock_calls allows us to measure the expected
    number of instantiations and method calls.
    """

    class Win(mock.MagicMock):
        load_theme = DumSig()
        icon = "icon"

    window = Win()

    with (
        mock.patch("mu.app.setup_logging") as set_log,
        mock.patch("mu.app.check_only_running_once"),
        mock.patch("mu.app.QApplication") as qa,
        mock.patch("mu.app.Editor") as ed,
        mock.patch("mu.app.Window", window) as win,
        mock.patch("sys.argv", ["mu"]),
        mock.patch("sys.exit") as ex,
        mock.patch("mu.app.QEventLoop") as mock_event_loop,
        mock.patch("mu.app.QThread"),
        mock.patch("mu.app.StartupWorker") as mock_worker,
        mock.patch("mu.app.setup_exception_handler") as mock_set_except,
    ):
        run()
        assert set_log.call_count == 1
        # foo.call_count is instantiating the class
        assert qa.call_count == 1
        # foo.mock_calls are method calls on the object
        # if hasattr(Qt, "AA_EnableHighDpiScaling"):
        #    assert len(qa.mock_calls) == 9
        # else:
        #    assert len(qa.mock_calls) == 8
        assert len(qa.mock_calls) == 7
        assert qsp.call_count == 1
        assert len(qsp.mock_calls) == 4
        assert ed.call_count == 1
        assert len(ed.mock_calls) == 4
        assert win.call_count == 1
        assert len(win.mock_calls) == 6
        assert ex.call_count == 1
        assert mock_event_loop.call_count == 1
        assert mock_worker.call_count == 1
        assert mock_set_except.call_count == 1
        window.load_theme.emit("day")
        qa.assert_has_calls([mock.call().setStyleSheet(DAY_STYLE)])
        window.load_theme.emit("night")
        qa.assert_has_calls([mock.call().setStyleSheet(NIGHT_STYLE)])
        window.load_theme.emit("contrast")
        qa.assert_has_calls([mock.call().setStyleSheet(CONTRAST_STYLE)])


def test_run_wayland_qt_qpa_platform_already_set():
    """
    Test that if is_linux_wayland() is True and QT_QPA_PLATFORM is already set,
    run() does not overwrite it.
    """
    with (
        mock.patch.dict(
            os.environ, {"QT_QPA_PLATFORM": "offscreen"}, clear=False
        ),
        mock.patch("mu.app.setup_logging"),
        mock.patch("mu.app.QApplication"),
        mock.patch("mu.app.Editor"),
        mock.patch("mu.app.Window"),
        mock.patch("sys.argv", ["mu"]),
        mock.patch("sys.exit"),
        mock.patch("mu.app.QEventLoop"),
        mock.patch("mu.app.QThread"),
        mock.patch("mu.app.StartupWorker"),
        mock.patch("mu.app.setup_exception_handler"),
        mock.patch("mu.app.is_linux_wayland", return_value=True),
    ):
        run()
        assert os.environ["QT_QPA_PLATFORM"] == "offscreen"


def test_run_sets_qt_qpa_platform_when_not_set():
    """
    Test that if is_linux_wayland() is True and QT_QPA_PLATFORM is not already set,
    run() sets the QT_QPA_PLATFORM environment variable to "wayland".
    """
    with (
        mock.patch.dict(os.environ, {}, clear=False),
        mock.patch("mu.app.setup_logging"),
        mock.patch("mu.app.QApplication"),
        mock.patch("mu.app.Editor"),
        mock.patch("mu.app.Window"),
        mock.patch("sys.argv", ["mu"]),
        mock.patch("sys.exit"),
        mock.patch("mu.app.QEventLoop"),
        mock.patch("mu.app.QThread"),
        mock.patch("mu.app.StartupWorker"),
        mock.patch("mu.app.setup_exception_handler"),
        mock.patch("mu.app.is_linux_wayland", return_value=True),
    ):
        run()
        assert os.environ.get("QT_QPA_PLATFORM") == "wayland"


def test_excepthook():
    """
    Test that custom excepthook logs error and calls sys.exit.
    """
    ex = Exception("BANG")
    exc_args = (type(ex), ex, ex.__traceback__)

    with (
        mock.patch("mu.app.logging.error") as error,
        mock.patch("mu.app.sys.exit") as exit,
        mock.patch("mu.app.webbrowser") as browser,
    ):
        excepthook(*exc_args)
        error.assert_called_once_with("Unrecoverable error", exc_info=exc_args)
        exit.assert_called_once_with(1)
        assert browser.open.call_count == 1


def test_excepthook_alamo():
    """
    If the crash reporting code itself encounters an error, then ensure this
    is logged before exiting.
    """
    ex = Exception("BANG")
    exc_args = (type(ex), ex, ex.__traceback__)

    mock_browser = mock.MagicMock()
    mock_browser.open.side_effect = RuntimeError("BROWSER BANG")

    with (
        mock.patch("mu.app.logging.error") as error,
        mock.patch("mu.app.sys.exit") as exit,
        mock.patch("mu.app.webbrowser", mock_browser),
    ):
        excepthook(*exc_args)
        assert error.call_count == 2
        exit.assert_called_once_with(1)


def test_excepthook_keyboard_interrupt():
    """
    Test that excepthook exits with code 0 for KeyboardInterrupt.
    """
    ex = KeyboardInterrupt()
    exc_args = (type(ex), ex, ex.__traceback__)

    with (
        mock.patch("mu.app.logging.error") as error,
        mock.patch("mu.app._shared_memory.release") as release,
        mock.patch("mu.app.sys.exit") as exit,
    ):
        excepthook(*exc_args)
        error.assert_called_once_with("Unrecoverable error", exc_info=exc_args)
        release.assert_called_once_with()
        exit.assert_called_once_with(0)


def test_debug():
    """
    Ensure the debugger is run with the expected arguments given the filename
    and other arguments passed in via sys.argv.
    """
    args = ("foo", "bar", "baz")
    filename = "foo.py"
    expected_filename = os.path.normcase(os.path.abspath(filename))
    mock_runner = mock.MagicMock()
    with mock.patch("mu.debugger.runner.run", mock_runner):
        mu_debug.debug(filename, *args)
        mock_runner.assert_called_once_with(
            "localhost", DEBUGGER_PORT, expected_filename, args
        )


def test_debug_no_args():
    """
    If the debugger is accidentally started with no filename and/or associated
    args, then emit a friendly message to indicate the problem.
    """
    expected_msg = "Debugger requires a Python script filename to run."
    mock_print = mock.MagicMock()
    with mock.patch("builtins.print", mock_print):
        mu_debug.debug()
        mock_print.assert_called_once_with(expected_msg)


def test_is_linux_wayland_true_xdg():
    """
    Test is_linux_wayland returns True when XDG_SESSION_TYPE is wayland.
    """
    with (
        mock.patch.dict(
            os.environ, {"XDG_SESSION_TYPE": "wayland"}, clear=False
        ),
        mock.patch("mu.app.platform.system", return_value="Linux"),
    ):
        assert is_linux_wayland() is True


def test_is_linux_wayland_true_wayland_display():
    """
    Test is_linux_wayland returns True when WAYLAND_DISPLAY contains 'wayland'.
    """
    with (
        mock.patch.dict(
            os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=False
        ),
        mock.patch("mu.app.platform.system", return_value="Linux"),
    ):
        assert is_linux_wayland() is True


def test_is_linux_wayland_false_not_linux():
    """
    Test is_linux_wayland returns False on non-Linux platforms.
    """
    with (
        mock.patch.dict(
            os.environ, {"XDG_SESSION_TYPE": "wayland"}, clear=False
        ),
        mock.patch("mu.app.platform.system", return_value="Windows"),
    ):
        assert is_linux_wayland() is False


def test_is_linux_wayland_false_env_not_wayland():
    """
    Test is_linux_wayland returns False when env vars do not contain 'wayland'.
    """
    with (
        mock.patch.dict(
            os.environ,
            {"XDG_SESSION_TYPE": "x11", "WAYLAND_DISPLAY": "somethingelse"},
            clear=False,
        ),
        mock.patch("mu.app.platform.system", return_value="Linux"),
    ):
        assert is_linux_wayland() is False


def test_running_twice():
    # try chaining instead of timing based stuff

    # Comment on the original test says:
    #
    #   It's important that the two competing processes are not part of the same
    #   process tree; otherwise the second attempt to acquire the mutex will
    #   succeed (which we don't want to happen for our purposes)
    #
    # However, on macOS it always seems to have the same parent process id and group
    # process id and this test seems to work on all platforms on CI.
    #
    cmd2 = "".join((
        "-c",
        "from mu import app;",
        "app.setup_exception_handler();",
        "app.check_only_running_once()",
        # should throw an exception and exit with code 2 if it's already running
    ))

    cmd1 = "".join((
        "-c",
        "import subprocess;",
        "import sys;",
        "from mu import app;",
        "app.setup_exception_handler();",
        "app.check_only_running_once();",
        # launch child process that will try to 'launch' the app again:
        'child2 = subprocess.run([sys.executable, "{0}"]);'.format(cmd2),
        # clean up and exit returning child process result code (which should be 2
        # if this 'already running' code is working)
        "app._shared_memory.release();",
        "exit(child2.returncode)",
    ))

    child1 = subprocess.run([sys.executable, cmd1])
    print("child 1 return code: {}".format(child1.returncode))
    assert child1.returncode == 2


def test_running_twice_after_generic_exception():
    """
    If we run and the app throws an exception, the exception handler
    should clean up shared memory sentinel and running again should succeed.
    """
    #
    # check_only_running_once() acquires shared memory block
    # raise uncaught exception to trigger exception handler
    # (subprocess should exit with exit code)
    # check to see if can run app again
    #

    # set show browser on crash suppression env for test
    with mock.patch.dict(
        os.environ, {"MU_SUPPRESS_CRASH_REPORT_FORM": "1"}, clear=False
    ):
        cmd1 = "".join((
            "-c",
            "import os;",
            "from mu import app;",
            "print('process 1 id: {}'.format(os.getpid()));",
            "app.setup_exception_handler();",
            "app.check_only_running_once();"
            "raise RuntimeError('intentional test exception')",
            # Intentionally do not manually release shared memory here.
            # Test is testing that exception handler does this.
        ))

        child1 = subprocess.run([sys.executable, cmd1])
        assert child1.returncode == 1
