# -*- coding: utf-8 -*-
"""
Tests for the Editor and REPL logic.
"""

import codecs
import contextlib
import json
import locale
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from unittest import mock

import pytest
from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

import mu.config
import mu.logic
import mu.settings

SESSION = json.dumps({
    "theme": "night",
    "mode": "python",
    "paths": ["path/foo.py", "path/bar.py"],
    "envars": [["name", "value"]],
})
ENCODING_COOKIE = "# -*- coding: {} -*-{}".format(
    mu.logic.ENCODING, mu.logic.NEWLINE
)


#
# Testing support functions
# These functions generate testing scenarios or mocks making
# the test more readable and easier to spot the element being
# tested from among the boilerplate setup code
#


def rstring(length=10, characters="abcdefghijklmnopqrstuvwxyz"):
    letters = list(characters)
    random.shuffle(letters)
    return "".join(letters[:length])


def _generate_python_files(contents, dirpath):
    """Generate a series of .py files, one for each element in an iterable

    contents should be an iterable (typically a list) containing one
    string for each of a the number of files to be created. The files
    will be created in the dirpath directory passed in which will neither
    be created nor destroyed by this function.
    """
    for i, c in enumerate(contents):
        name = uuid.uuid1().hex
        filepath = os.path.join(dirpath, "%03d-%s.py" % (1 + i, name))
        #
        # Write using newline="" so line-ending tests can work!
        # If a binary write is needed (eg for an encoding test) pass
        # a list of empty strings as contents and then write the bytes
        # as part of the test.
        #
        with open(filepath, "w", encoding=mu.logic.ENCODING, newline="") as f:
            f.write(c)
        yield filepath


@contextlib.contextmanager
def generate_python_file(text="", dirpath=None):
    """
    Create a temp directory and populate it with on .py file, then remove it.
    """
    dirpath = dirpath or tempfile.mkdtemp(prefix="mu-")
    for filepath in _generate_python_files([text], dirpath):
        yield filepath
        break
    shutil.rmtree(dirpath)


@contextlib.contextmanager
def generate_session(
    theme="day",
    mode="python",
    file_contents=None,
    envars=[["name", "value"]],
    microbit_runtime=None,
    zoom_level=2,
    window=None,
    **kwargs,
):
    """Generate a temporary session file for one test

    By default, the session file will be created inside a temporary directory
    which will be removed afterwards. If filepath is specified the session
    file will be created with that fully-specified path and filename.

    If an iterable of file contents is specified (referring to text files to
    be reloaded from a previous session) then files will be created in the
    a directory with the contents provided.

    If None is passed to any of the parameters that item will not be included
    in the session data. Once all parameters have been considered if no session
    data is present, the file will *not* be created.

    Any additional kwargs are created as items in the data (eg to generate
    invalid file contents)

    The mu.logic.get_session_path function is mocked to return the
    temporary filepath from this session.

    The session is yielded to the contextmanager so the typical usage is:

    with generate_session(mode="night") as session:
        # do some test
        assert <whatever>.mode == session['mode']
    """
    dirpath = tempfile.mkdtemp(prefix="mu-")
    session_data = {}
    if theme:
        session_data["theme"] = theme
    if mode:
        session_data["mode"] = mode
    if file_contents:
        paths = _generate_python_files(file_contents, dirpath)
        session_data["paths"] = list(paths)
    if envars:
        session_data["envars"] = envars
    if microbit_runtime:
        session_data["microbit_runtime"] = microbit_runtime
    if zoom_level:
        session_data["zoom_level"] = zoom_level
    if window:
        session_data["window"] = window
    session_data.update(**kwargs)

    session = mu.settings.SessionSettings()
    session.reset()
    session.update(session_data)

    with mock.patch("mu.settings.session", session):
        yield session

    shutil.rmtree(dirpath)


def mocked_view(text, path, newline):
    """Create a mocked view with path, newline and text"""
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = path
    view.current_tab.newline = newline
    view.current_tab.text = mock.MagicMock(return_value=text)

    view.add_tab = mock.MagicMock()
    view.get_save_path = mock.MagicMock(return_value=path)
    view.get_load_path = mock.MagicMock()
    view.add_tab = mock.MagicMock()
    return view


def mocked_editor(mode="python", text=None, path=None, newline=None):
    """Return a mocked editor with a mocked view

    This is intended to assist the several tests where a mocked editor
    is needed but where the length of setup code to get there tends to
    obscure the intent of the test
    """
    view = mocked_view(text, path, newline)
    ed = mu.logic.Editor(view)
    ed.select_mode = mock.MagicMock()
    mock_mode = mock.MagicMock()
    mock_mode.save_timeout = 5
    mock_mode.workspace_dir.return_value = "/fake/path"
    mock_mode.api.return_value = ["API Specification"]
    ed.modes = {mode: mock_mode}
    return ed


@pytest.fixture
def mocked_session():
    """Mock the save-session functionality"""
    with mock.patch.object(mu.settings, "session") as mocked_session:
        yield mocked_session


def test_CONSTANTS():
    """
    Ensure the expected constants exist.
    """
    assert mu.config.HOME_DIRECTORY
    assert mu.config.DATA_DIR
    assert mu.config.WORKSPACE_NAME


@pytest.fixture
def microbit_com1():
    microbit = mu.logic.Device(
        0x0D28,
        0x0204,
        "COM1",
        123456,
        "ARM",
        "BBC micro:bit",
        "microbit",
        "BBC micro:bit",
    )
    return microbit


@pytest.fixture
def microbit_com2():
    microbit = mu.logic.Device(
        0x0D28,
        0x0204,
        "COM2",
        123456,
        "ARM",
        "BBC micro:bit",
        "microbit",
        "BBC micro:bit",
    )
    return microbit


@pytest.fixture
def adafruit_feather():
    adafruit_feather = mu.logic.Device(
        0x239A,
        0x800B,
        "COM1",
        123456,
        "ARM",
        "CircuitPython",
        "circuitpython",
        "Adafruit Feather",
    )
    return adafruit_feather


@pytest.fixture
def esp_device():
    esp_device = mu.logic.Device(
        0x0403,
        0x6015,
        "COM1",
        123456,
        "Sparkfun",
        "ESP MicroPython",
        "esp",
        # No board_name specified
    )
    return esp_device


def test_write_and_flush():
    """
    Ensure the write and flush function tries to write to the filesystem and
    flush so the write happens immediately.
    """
    mock_fd = mock.MagicMock()
    mock_content = mock.MagicMock()
    with mock.patch("mu.logic.os.fsync") as fsync:
        mu.logic.write_and_flush(mock_fd, mock_content)
        fsync.assert_called_once_with(mock_fd)
    mock_fd.write.assert_called_once_with(mock_content)
    mock_fd.flush.assert_called_once_with()


def test_save_and_encode():
    """
    When saving, ensure that encoding cookies are honoured, otherwise fall back
    to the default encoding (UTF-8 -- as per Python standard practice).
    """
    encoding_cookie = "# -*- coding: latin-1 -*-"
    text = encoding_cookie + '\n\nprint("Hello")'
    mock_open = mock.MagicMock()
    mock_wandf = mock.MagicMock()
    # Valid cookie
    with (
        mock.patch("mu.logic.open", mock_open),
        mock.patch("mu.logic.write_and_flush", mock_wandf),
    ):
        mu.logic.save_and_encode(text, "foo.py")
    mock_open.assert_called_once_with(
        "foo.py", "w", encoding="latin-1", newline=""
    )
    assert mock_wandf.call_count == 1
    mock_open.reset_mock()
    mock_wandf.reset_mock()
    # Invalid cookie
    encoding_cookie = "# -*- coding: utf-42 -*-"
    text = encoding_cookie + '\n\nprint("Hello")'
    with (
        mock.patch("mu.logic.open", mock_open),
        mock.patch("mu.logic.write_and_flush", mock_wandf),
    ):
        mu.logic.save_and_encode(text, "foo.py")
    mock_open.assert_called_once_with(
        "foo.py", "w", encoding=mu.logic.ENCODING, newline=""
    )
    assert mock_wandf.call_count == 1
    mock_open.reset_mock()
    mock_wandf.reset_mock()
    # No cookie
    text = 'print("Hello")'
    with (
        mock.patch("mu.logic.open", mock_open),
        mock.patch("mu.logic.write_and_flush", mock_wandf),
    ):
        mu.logic.save_and_encode(text, "foo.py")
    mock_open.assert_called_once_with(
        "foo.py", "w", encoding=mu.logic.ENCODING, newline=""
    )
    assert mock_wandf.call_count == 1


def test_sniff_encoding_from_BOM():
    """
    Ensure an expected BOM detected at the start of the referenced file is
    used to set the expected encoding.
    """
    with mock.patch(
        "mu.logic.open", mock.mock_open(read_data=codecs.BOM_UTF8 + b"# hello")
    ):
        assert mu.logic.sniff_encoding("foo.py") == "utf-8-sig"


def test_sniff_encoding_from_cookie():
    """
    If there's a cookie present, then use that to work out the expected
    encoding.
    """
    encoding_cookie = b"# -*- coding: latin-1 -*-"
    mock_locale = mock.MagicMock()
    mock_locale.getpreferredencoding.return_value = "UTF-8"
    with (
        mock.patch("mu.logic.open", mock.mock_open(read_data=encoding_cookie)),
        mock.patch("mu.logic.locale", mock_locale),
    ):
        assert mu.logic.sniff_encoding("foo.py") == "latin-1"


def test_sniff_encoding_from_bad_cookie_encoding():
    """
    If there's a cookie present but we can't even read it, then return None.
    """
    encoding_cookie = "# -*- coding: silly-你好 -*-".encode("utf-8")
    mock_locale = mock.MagicMock()
    mock_locale.getpreferredencoding.return_value = "ascii"
    with (
        mock.patch("mu.logic.open", mock.mock_open(read_data=encoding_cookie)),
        mock.patch("mu.logic.locale", mock_locale),
    ):
        assert mu.logic.sniff_encoding("foo.py") is None


def test_sniff_encoding_from_bad_cookie_name():
    """
    If there's a cookie present but we can't even read it, then return None.
    """
    encoding_cookie = "# -*- coding: invalid-codec -*-".encode("utf-8")
    mock_locale = mock.MagicMock()
    mock_locale.getpreferredencoding.return_value = "utf-8"
    with (
        mock.patch("mu.logic.open", mock.mock_open(read_data=encoding_cookie)),
        mock.patch("mu.logic.locale", mock_locale),
    ):
        assert mu.logic.sniff_encoding("foo.py") is None


def test_sniff_encoding_fallback_to_locale():
    """
    If there's no encoding information in the file, just return None.
    """
    mock_locale = mock.MagicMock()
    mock_locale.getpreferredencoding.return_value = "ascii"
    with (
        mock.patch("mu.logic.open", mock.mock_open(read_data=b"# hello")),
        mock.patch("mu.logic.locale", mock_locale),
    ):
        assert mu.logic.sniff_encoding("foo.py") is None


def test_sniff_newline_convention():
    """
    Ensure sniff_newline_convention returns the expected newline convention.
    """
    text = "the\r\ncat\nsat\non\nthe\r\nmat"
    assert mu.logic.sniff_newline_convention(text) == "\n"


def test_sniff_newline_convention_local():
    """
    Ensure sniff_newline_convention returns the local newline convention if it
    cannot determine it from the text.
    """
    text = "There are no new lines here"
    assert mu.logic.sniff_newline_convention(text) == os.linesep


def test_extract_envars():
    """
    Given a correct textual representation, get the expected list
    representation of user defined environment variables.
    """
    raw = "FOO=BAR\n BAZ = Q=X    \n\n\n"
    expected = mu.logic.extract_envars(raw)
    assert expected == {"FOO": "BAR", "BAZ": "Q=X"}


def test_check_flake():
    """
    Ensure the check_flake method calls PyFlakes with the expected code
    reporter.
    """
    mock_r = mock.MagicMock()
    mock_r.log = [{"line_no": 2, "column": 0, "message": "b"}]
    with (
        mock.patch("mu.logic.MuFlakeCodeReporter", return_value=mock_r),
        mock.patch("mu.logic.check", return_value=None) as mock_check,
    ):
        result = mu.logic.check_flake("foo.py", "some code")
        assert result == {2: mock_r.log}
        mock_check.assert_called_once_with("some code", "foo.py", mock_r)


def test_check_flake_needing_expansion():
    """
    Ensure the check_flake method calls PyFlakes with the expected code
    reporter.
    """
    mock_r = mock.MagicMock()
    msg = "'microbit.foo' imported but unused"
    mock_r.log = [{"line_no": 2, "column": 0, "message": msg}]
    with (
        mock.patch("mu.logic.MuFlakeCodeReporter", return_value=mock_r),
        mock.patch("mu.logic.check", return_value=None) as mock_check,
    ):
        code = "from microbit import *"
        result = mu.logic.check_flake("foo.py", code)
        assert result == {}
        mock_check.assert_called_once_with(
            mu.logic.EXPANDED_IMPORT, "foo.py", mock_r
        )


def test_check_flake_with_builtins():
    """
    If a list of assumed builtin symbols is passed, any "undefined name"
    messages for them are ignored.
    """
    mock_r = mock.MagicMock()
    mock_r.log = [
        {"line_no": 2, "column": 0, "message": "undefined name 'foo'"}
    ]
    with (
        mock.patch("mu.logic.MuFlakeCodeReporter", return_value=mock_r),
        mock.patch("mu.logic.check", return_value=None) as mock_check,
    ):
        result = mu.logic.check_flake("foo.py", "some code", builtins=["foo"])
        assert result == {}
        mock_check.assert_called_once_with("some code", "foo.py", mock_r)


def test_check_real_flake_output_with_builtins():
    """
    Check that passing builtins correctly suppresses undefined name errors
    using real .check_flake() output.
    """
    ok_result = mu.logic.check_flake("foo.py", "print(foo)", builtins=["foo"])
    assert ok_result == {}
    bad_result = mu.logic.check_flake("foo.py", "print(bar)", builtins=["foo"])
    assert len(bad_result) == 1


def test_check_pycodestyle_E121():
    """
    Ensure the expected result is generated from the PEP8 style validator.
    Should ensure we honor a mu internal override of E123 error
    """
    code = "mylist = [\n 1, 2,\n 3, 4,\n ]"  # would have Generated E123
    result = mu.logic.check_pycodestyle(code)
    assert len(result) == 0


def test_check_pycodestyle_custom_override():
    """
    Ensure the expected result if generated from the PEP8 style validator.
    For this test we have overridden the E265 error check via a custom
    override "pycodestyle" file in a directory pointed to by the content of
    scripts/codecheck.ini. We should "not" get and E265 error due to the
    lack of space after the #
    """
    code = "# OK\n#this is ok if we override the E265 check\n"
    result = mu.logic.check_pycodestyle(code, "tests/scripts/pycodestyle")
    assert len(result) == 0


def test_check_pycodestyle():
    """
    Ensure the expected result if generated from the PEP8 style validator.
    """
    code = "import foo\n\n\n\n\n\ndef bar():\n    pass\n"  # Generate E303
    result = mu.logic.check_pycodestyle(code)
    assert len(result) == 1
    assert result[6][0]["line_no"] == 6
    assert result[6][0]["column"] == 0
    assert " above this line" in result[6][0]["message"]
    assert result[6][0]["code"] == "E303"


def test_check_pycodestyle_with_non_ascii():
    """
    Ensure pycodestyle can at least see a file with non-ASCII characters
    """
    code = "x='\u2005'\n"
    mu.logic.check_pycodestyle(code)
    #
    # Doesn't actually matter what pycodestyle returns; we just want to make
    # sure it didn't error out
    #


def test_MuFlakeCodeReporter_init():
    """
    Check state is set up as expected.
    """
    r = mu.logic.MuFlakeCodeReporter()
    assert r.log == []


def test_MuFlakeCodeReporter_unexpected_error():
    """
    Check the reporter handles unexpected errors.
    """
    r = mu.logic.MuFlakeCodeReporter()
    r.unexpectedError("foo.py", "Nobody expects the Spanish Inquisition!")
    assert len(r.log) == 1
    assert r.log[0]["line_no"] == 0
    assert r.log[0]["filename"] == "foo.py"
    assert r.log[0]["message"] == "Nobody expects the Spanish Inquisition!"


def test_MuFlakeCodeReporter_syntax_error():
    """
    Check the reporter handles syntax errors in a humane and kid friendly
    manner.
    """
    msg = (
        "Syntax error. Python cannot understand this line. Check for "
        "missing characters!"
    )
    r = mu.logic.MuFlakeCodeReporter()
    r.syntaxError(
        "foo.py", "something incomprehensible to kids", "2", 3, "source"
    )
    assert len(r.log) == 1
    assert r.log[0]["line_no"] == 1
    assert r.log[0]["message"] == msg
    assert r.log[0]["column"] == 2
    assert r.log[0]["source"] == "source"


def test_MuFlakeCodeReporter_flake_matched():
    """
    Check the reporter handles flake (regular) errors that match the expected
    message structure.
    """
    r = mu.logic.MuFlakeCodeReporter()
    err = "foo.py:4:0 something went wrong"
    r.flake(err)
    assert len(r.log) == 1
    assert r.log[0]["line_no"] == 3
    assert r.log[0]["column"] == 0
    assert r.log[0]["message"] == "something went wrong"


def test_MuFlakeCodeReporter_flake_real_output():
    """
    Check the reporter handles real output from flake, to catch format
    change regressions.
    """
    check = mu.logic.check
    reporter = mu.logic.MuFlakeCodeReporter()
    code = "a = 1\nb = 2\nc\n"
    check(code, "filename", reporter)
    assert reporter.log[0]["line_no"] == 2
    assert reporter.log[0]["message"] == "undefined name 'c'"
    assert reporter.log[0]["column"] == 1


def test_MuFlakeCodeReporter_flake_un_matched():
    """
    Check the reporter handles flake errors that do not conform to the expected
    message structure.
    """
    r = mu.logic.MuFlakeCodeReporter()
    err = "something went wrong"
    r.flake(err)
    assert len(r.log) == 1
    assert r.log[0]["line_no"] == 0
    assert r.log[0]["column"] == 0
    assert r.log[0]["message"] == "something went wrong"


def test_device__init(adafruit_feather):
    assert adafruit_feather.vid == 0x239A
    assert adafruit_feather.pid == 0x800B
    assert adafruit_feather.port == "COM1"
    assert adafruit_feather.serial_number == 123456
    assert adafruit_feather.manufacturer == "ARM"
    assert adafruit_feather.long_mode_name == "CircuitPython"
    assert adafruit_feather.short_mode_name == "circuitpython"
    assert adafruit_feather.board_name == "Adafruit Feather"


def test_device_name(esp_device, adafruit_feather):
    """
    Test that devices without a boardname (such as the esp_device),
    are the long mode name with " compatible" appended
    """
    assert esp_device.name == "ESP MicroPython compatible"
    assert adafruit_feather.name == "Adafruit Feather"


def test_device_equality(microbit_com1):
    assert microbit_com1 == microbit_com1


def test_device_inequality(microbit_com1, microbit_com2):
    assert microbit_com1 != microbit_com2


def test_device_ordering_lt(microbit_com1, adafruit_feather):
    assert adafruit_feather < microbit_com1


def test_device_ordering_gt(microbit_com1, adafruit_feather):
    assert microbit_com1 > adafruit_feather


def test_device_ordering_le(microbit_com1, adafruit_feather):
    assert adafruit_feather <= microbit_com1


def test_device_ordering_ge(microbit_com1, adafruit_feather):
    assert microbit_com1 >= adafruit_feather


def test_device_to_string(adafruit_feather):
    assert (
        str(adafruit_feather)
        == "Adafruit Feather on COM1 (VID: 0x239A, PID: 0x800B)"
    )


def test_device_hash(microbit_com1, microbit_com2):
    assert hash(microbit_com1) == hash(microbit_com1)
    assert hash(microbit_com1) != hash(microbit_com2)


def test_devicelist_index(microbit_com1):
    modes = {}
    dl = mu.logic.DeviceList(modes)
    dl.add_device(microbit_com1)
    assert dl[0] == microbit_com1


def test_devicelist_length(microbit_com1, microbit_com2):
    modes = {}
    dl = mu.logic.DeviceList(modes)
    assert len(dl) == 0
    dl.add_device(microbit_com1)
    assert len(dl) == 1
    dl.add_device(microbit_com2)
    assert len(dl) == 2


def test_devicelist_rowCount(microbit_com1, microbit_com2):
    modes = {}
    dl = mu.logic.DeviceList(modes)
    assert dl.rowCount(None) == 0
    dl.add_device(microbit_com1)
    assert dl.rowCount(None) == 1
    dl.add_device(microbit_com2)
    assert dl.rowCount(None) == 2


def test_devicelist_data(microbit_com1, adafruit_feather):
    modes = {}
    dl = mu.logic.DeviceList(modes)
    dl.add_device(microbit_com1)
    dl.add_device(adafruit_feather)
    tooltip = dl.data(dl.index(0), Qt.ToolTipRole)
    display = dl.data(dl.index(0), Qt.DisplayRole)
    assert display == adafruit_feather.name
    assert tooltip == str(adafruit_feather)
    tooltip = dl.data(dl.index(1), Qt.ToolTipRole)
    display = dl.data(dl.index(1), Qt.DisplayRole)
    assert display == microbit_com1.name
    assert tooltip == str(microbit_com1)


def test_devicelist_add_device_in_sorted_order(
    microbit_com1, adafruit_feather
):
    modes = {}
    dl = mu.logic.DeviceList(modes)
    dl.add_device(microbit_com1)
    assert dl[0] == microbit_com1
    dl.add_device(adafruit_feather)
    assert dl[0] == adafruit_feather
    assert dl[1] == microbit_com1

    xyz_device = mu.logic.Device(
        0x123B, 0x333A, "COM1", 123456, "ARM", "ESP Mode", "esp", "xyz"
    )
    dl.add_device(xyz_device)
    assert dl[2] == xyz_device


def test_devicelist_remove_device(microbit_com1, adafruit_feather):
    modes = {}
    dl = mu.logic.DeviceList(modes)
    dl.add_device(microbit_com1)
    assert len(dl) == 1
    dl.remove_device(microbit_com1)
    assert len(dl) == 0

    dl.add_device(microbit_com1)
    dl.add_device(adafruit_feather)
    assert len(dl) == 2
    dl.remove_device(adafruit_feather)
    assert len(dl) == 1
    dl.remove_device(microbit_com1)
    assert len(dl) == 0


def test_editor_init():
    """
    Ensure a new instance is set-up correctly and creates the required folders
    upon first start.
    """
    view = mock.MagicMock()
    # Check the editor attempts to create required directories if they don't
    # already exist.
    with (
        mock.patch("os.path.exists", return_value=False),
        mock.patch("os.makedirs", return_value=None) as mkd,
    ):
        e = mu.logic.Editor(view)
        assert e._view == view
        assert e.theme == "day"
        assert e.mode == "python"
        assert e.modes == {}
        assert e.envars == {}
        assert e.microbit_runtime == ""
        # assert e.connected_devices == set()
        assert e.find == ""
        assert e.replace == ""
        assert e.global_replace is False
        assert e.selecting_mode is False
        assert mkd.call_count == 1
        assert mkd.call_args_list[0][0][0] == mu.logic.DATA_DIR


def test_editor_setup():
    """
    An editor should have a modes attribute.
    """
    view = mock.MagicMock()
    e = mu.logic.Editor(view)
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "foo"
    mock_modes = {"python": mock_mode}
    with (
        mock.patch("os.path.exists", return_value=False),
        mock.patch("os.makedirs", return_value=None) as mkd,
        mock.patch("shutil.copy") as mock_shutil_copy,
        mock.patch("shutil.copytree") as mock_shutil_copytree,
    ):
        e.setup(mock_modes)
        assert mkd.call_count == 5
        assert mkd.call_args_list[0][0][0] == "foo"
        asset_len = len(mu.logic.DEFAULT_IMAGES) + len(mu.logic.DEFAULT_SOUNDS)
        assert mock_shutil_copy.call_count == asset_len
        assert mock_shutil_copytree.call_count == 2
    assert e.modes == mock_modes
    view.set_usb_checker.assert_called_once_with(
        1, e.connected_devices.check_usb
    )


def test_editor_connect_to_status_bar():
    """
    Check that the Window status bar is connected appropriately
    to Editor-pane and to modes
    """
    view = mock.MagicMock()
    e = mu.logic.Editor(view)
    mock_python_mode = mock.MagicMock()
    mock_esp_mode = mock.MagicMock()
    mock_python_mode.workspace_dir.return_value = "foo"
    mock_modes = {"python": mock_python_mode, "esp": mock_esp_mode}
    mock_device_selector = mock.MagicMock()
    with (
        mock.patch("os.path.exists", return_value=False),
        mock.patch("os.makedirs", return_value=None),
        mock.patch("shutil.copy"),
        mock.patch("shutil.copytree"),
    ):
        e.setup(mock_modes)
        sb = mock.MagicMock()
        sb.device_selector = mock_device_selector
        e.connect_to_status_bar(sb)
        # Check device_changed signal is connected to both editor and modes
        assert sb.device_selector.device_changed.connect.call_count == 3


def test_editor_restore_session_existing_runtime():
    """
    A correctly specified session is restored properly.
    """
    mode, theme = "python", "night"
    file_contents = ["", ""]
    ed = mocked_editor(mode)
    with mock.patch("os.path.isfile", return_value=True):
        with generate_session(
            theme,
            mode,
            file_contents,
            microbit_runtime="/foo",
            zoom_level=5,
        ):
            ed.restore_session()

    assert ed.theme == theme
    assert ed._view.add_tab.call_count == len(file_contents)
    ed._view.set_theme.assert_called_once_with(theme)
    assert ed.envars == {"name": "value"}
    assert ed.microbit_runtime == "/foo"
    assert ed._view.zoom_position == 5


def test_editor_restore_session_missing_runtime():
    """
    If the referenced microbit_runtime file doesn't exist, reset to '' so Mu
    uses the built-in runtime.
    """
    mode, theme = "python", "night"
    file_contents = ["", ""]
    ed = mocked_editor(mode)

    with generate_session(theme, mode, file_contents, microbit_runtime="/foo"):
        ed.restore_session()

    assert ed.theme == theme
    assert ed._view.add_tab.call_count == len(file_contents)
    ed._view.set_theme.assert_called_once_with(theme)
    assert ed.envars == {"name": "value"}
    assert ed.microbit_runtime == ""  # File does not exist so set to ''


def test_editor_restore_session_missing_files():
    """
    Missing files that were opened tabs in the previous session are safely
    ignored when attempting to restore them.
    """
    mode, theme = "python", "night"
    ed = mocked_editor(mode)

    with generate_session(theme, mode) as session:
        session["paths"] = ["*does not exist*"]
        ed.restore_session()

    assert ed._view.add_tab.call_count == 0


def test_editor_restore_session_invalid_mode():
    """
    As Mu's modes are added and/or renamed, invalid mode names may need to be
    ignored (this happens regularly when changing versions when developing
    Mu itself).
    """
    valid_mode, invalid_mode = "python", uuid.uuid1().hex
    ed = mocked_editor(valid_mode)
    with generate_session(mode=invalid_mode):
        ed.restore_session()
    ed.select_mode.assert_called_once_with(None)


def test_editor_restore_session_no_session_file():
    """
    If there's no prior session file (such as upon first start) then simply
    start up the editor with an empty untitled tab.

    Strictly, this isn't now a check for no session file but for an
    empty session object (which might have arisen from no file)
    """
    ed = mocked_editor()
    ed._view.tab_count = 0
    ed._view.add_tab = mock.MagicMock()
    session = mu.settings.SessionSettings()
    filepath = os.path.abspath(rstring())
    assert not os.path.exists(filepath)
    session.load(filepath)

    with mock.patch.object(mu.settings, "session", session):
        ed.restore_session()

    assert ed._view.add_tab.call_count == 1
    ed.select_mode.assert_called_once_with(None)


def test_editor_restore_session_invalid_file(tmp_path):
    """
    A malformed JSON file is correctly detected and app behaves the same as if
    there was no session file.
    """
    ed = mocked_editor()
    ed._view.tab_count = 0
    ed._view.add_tab = mock.MagicMock()
    session = mu.settings.SessionSettings()
    filepath = os.path.join(str(tmp_path), rstring())
    with open(filepath, "w") as f:
        f.write(rstring())
    session.load(filepath)

    with mock.patch.object(mu.settings, "session", session):
        ed.restore_session()

    assert ed._view.add_tab.call_count == 1
    ed.select_mode.assert_called_once_with(None)


def test_editor_restore_sessionopen_tabs_in_the_same_order():
    """
    Editor.restore_session() loads editor tabs in the same order as the 'paths'
    array in the session.json file.
    """
    ed = mocked_editor()
    ed.direct_load = mock.MagicMock()
    settings_paths = ["a.py", "b.py", "c.py", "d.py"]
    with generate_session(paths=settings_paths):
        ed.restore_session()

    direct_load_calls_args = [
        os.path.basename(args[0])
        for args, _kwargs in ed.direct_load.call_args_list
    ]
    assert direct_load_calls_args == settings_paths


def test_editor_restore_sessiondefer_launch_paths():
    """
    Editor.restore_session() should defer loading files that are present in launch_paths.
    """
    ed = mocked_editor()
    ed.direct_load = mock.MagicMock()
    session_paths = ["a.py", "b.py", "c.py"]
    launch_paths = ["b.py"]
    with generate_session(paths=session_paths):
        ed.restore_session(paths=launch_paths)

    direct_load_calls_args = [
        os.path.basename(args[0])
        for args, _kwargs in ed.direct_load.call_args_list
    ]
    expected_paths = ["a.py", "c.py", "b.py"]
    assert direct_load_calls_args == expected_paths


def test_editor_restore_session_list_envars():
    """
    If envars is a list in the old session, convert it to a dict.
    """
    ed = mocked_editor()
    with generate_session(envars=[["name", "value"]]):
        ed.restore_session()

    assert ed.envars == {"name": "value"}


def test_editor_restore_session_duplicated_list_envars():
    """
    If envars is a list with duplicates in the old session, convert it to a
    dict of unique entries.
    """
    ed = mocked_editor()
    with generate_session(
        envars=[
            ["name", "value"],
            ["name", "value"],
            ["name2", "value2"],
            ["name2", "value2"],
        ]
    ):
        ed.restore_session()

    assert ed.envars == {"name": "value", "name2": "value2"}


def test_editor_restore_sessionsets_python_anywhere_fields():
    """
    Ensure that restore_session sets pa_username, pa_token, pa_instance
    from python_anywhere session data.
    """
    ed = mocked_editor()
    pa_data = {
        "username": "testuser",
        "token": "testtoken",
        "instance": "testinstance",
    }
    with generate_session(python_anywhere=pa_data):
        ed.restore_session()
    assert ed.pa_username == "testuser"
    assert ed.pa_token == "testtoken"
    assert ed.pa_instance == "testinstance"


def test_editor_restore_sessionsets_locale():
    """
    Ensure that Editor.restore_session sets user_locale and calls i18n.set_language
    when 'locale' is present in the session.
    """
    mode = "python"
    ed = mocked_editor(mode)
    test_locale = "zh_CN"
    with (
        mock.patch("mu.i18n.set_language") as mock_set_language,
        mock.patch("mu.logic.settings") as mock_settings,
    ):
        mock_settings.session = {"locale": test_locale}
        ed.restore_session()
        assert ed.user_locale == test_locale
        mock_set_language.assert_called_once_with(test_locale)


def test_editor_restore_saved_window_geometry():
    """
    Window geometry specified in the session file is restored properly.
    """
    ed = mocked_editor()
    window = {"x": 10, "y": 20, "w": 1000, "h": 600}
    with mock.patch("os.path.isfile", return_value=True):
        with generate_session(window=window):
            ed.restore_session()
    ed._view.size_window.assert_called_once_with(**window)


def test_editor_restore_default_window_geometry():
    """
    Window is sized by default if no geometry exists in the session file.
    """
    ed = mocked_editor()
    with mock.patch("os.path.isfile", return_value=True):
        with generate_session():
            ed.restore_session()
    ed._view.size_window.assert_called_once_with()


def test_editor_open_focus_passed_file():
    """
    A file passed in by the OS is opened
    """
    ed = mocked_editor()
    ed.direct_load = mock.MagicMock()
    filepath = uuid.uuid1().hex
    with generate_session():
        ed.restore_session(paths=[filepath])

    ed.direct_load.assert_called_with(os.path.abspath(filepath))


def test_editor_session_and_open_focus_passed_file():
    """
    A passed in file is merged with session, opened last
    so it receives focus
    It will be the middle position in the session
    """
    ed = mocked_editor()
    ed.direct_load = mock.MagicMock()
    filepath = os.path.abspath(uuid.uuid1().hex)
    with generate_session(file_contents=[""]) as session:
        ed.restore_session(paths=[filepath])

    args_only = [args for (args, _) in ed.direct_load.call_args_list]
    call_args = [a[0] for a in args_only]
    expected_call_args = session["paths"] + [filepath]
    assert call_args == expected_call_args


def test_toggle_theme_to_night():
    """
    The current theme is 'day' so toggle to night. Expect the state to be
    updated and the appropriate call to the UI layer is made.
    """
    view = mock.MagicMock()
    view.set_theme = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.theme = "day"
    ed.toggle_theme()
    assert ed.theme == "night"
    view.set_theme.assert_called_once_with(ed.theme)


def test_toggle_theme_to_day():
    """
    The current theme is 'contrast' so toggle to day. Expect the state to be
    updated and the appropriate call to the UI layer is made.
    """
    view = mock.MagicMock()
    view.set_theme = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.theme = "contrast"
    ed.toggle_theme()
    assert ed.theme == "day"
    view.set_theme.assert_called_once_with(ed.theme)


def test_toggle_theme_to_contrast():
    """
    The current theme is 'night' so toggle to contrast. Expect the state to be
    updated and the appropriate call to the UI layer is made.
    """
    view = mock.MagicMock()
    view.set_theme = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.theme = "night"
    ed.toggle_theme()
    assert ed.theme == "contrast"
    view.set_theme.assert_called_once_with(ed.theme)


def test_new():
    """
    Ensure an untitled tab is added to the UI.
    """
    view = mock.MagicMock()
    view.add_tab = mock.MagicMock()
    mock_mode = mock.MagicMock()
    api = ["API specification"]
    mock_mode.api.return_value = api
    mock_mode.code_template = "new code template" + mu.logic.NEWLINE
    ed = mu.logic.Editor(view)
    ed.modes = {"python": mock_mode}
    ed.new()
    py = mock_mode.code_template + mu.logic.NEWLINE
    view.add_tab.assert_called_once_with(None, py, api, mu.logic.NEWLINE)


def test_load_checks_file_exists():
    """
    If the passed in path does not exist, this is logged and no other side
    effect happens.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    with (
        mock.patch("os.path.isfile", return_value=False),
        mock.patch("mu.logic.logger.info") as mock_info,
    ):
        ed._load("not_a_file")
        msg1 = "Loading script from: not_a_file"
        msg2 = "The file not_a_file does not exist."
        assert mock_info.call_args_list[0][0][0] == msg1
        assert mock_info.call_args_list[1][0][0] == msg2


def test_load_python_file():
    """
    If the user specifies a Python file (*.py) then ensure it's loaded and
    added as a tab.
    """
    text, newline = "python", "\n"
    ed = mocked_editor()
    with generate_python_file(text) as filepath:
        ed._view.get_load_path.return_value = filepath
        with mock.patch("mu.logic.read_and_decode") as mock_read:
            mock_read.return_value = text, newline
            ed.load()

    mock_read.assert_called_once_with(filepath)
    ed._view.add_tab.assert_called_once_with(
        filepath, text, ed.modes[ed.mode].api(), newline
    )


def test_load_python_file_case_insensitive_file_type():
    """
    If the user specifies a Python file (*.PY) then ensure it's loaded and
    added as a tab.
    """
    text, newline = "python", "\n"
    ed = mocked_editor()
    with generate_python_file(text) as filepath:
        ed._view.get_load_path.return_value = filepath.upper()
        with (
            mock.patch("mu.logic.read_and_decode") as mock_read,
            mock.patch("os.path.isfile", return_value=True),
        ):
            mock_read.return_value = text, newline
            ed.load()

    mock_read.assert_called_once_with(filepath.upper())
    ed._view.add_tab.assert_called_once_with(
        filepath.upper(), text, ed.modes[ed.mode].api(), newline
    )


def test_load_python_unicode_error():
    """
    If Mu encounters a UnicodeDecodeError when trying to read and decode the
    file, it should display a helpful message explaining the problem.
    """
    text = "not utf encoded content"
    ed = mocked_editor()
    with generate_python_file(text) as filepath:
        ed._view.get_load_path.return_value = filepath
        with mock.patch("mu.logic.read_and_decode") as mock_read:
            mock_read.side_effect = UnicodeDecodeError(
                "funnycodec", b"\x00\x00", 1, 2, "A fake reason!"
            )
            ed.load()
    assert ed._view.show_message.call_count == 1


def test_no_duplicate_load_python_file():
    """
    If the user specifies a file already loaded, ensure this is detected.
    """
    brown_script = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "scripts",
        "contains_brown.py",
    )

    editor_window = mock.MagicMock()
    editor_window.show_message = mock.MagicMock()
    editor_window.focus_tab = mock.MagicMock()
    editor_window.add_tab = mock.MagicMock()

    brown_tab = mock.MagicMock()
    brown_tab.path = brown_script
    unsaved_tab = mock.MagicMock()
    unsaved_tab.path = None

    editor_window.widgets = [unsaved_tab, brown_tab]

    editor_window.get_load_path = mock.MagicMock(return_value=brown_script)
    editor_window.current_tab.path = "path"
    # Create the "editor" that'll control the "window".
    editor = mu.logic.Editor(view=editor_window)
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "/fake/path"
    editor.modes = {"python": mock_mode}
    editor.load()
    message = 'The file "{}" is already open.'.format(
        os.path.basename(brown_script)
    )
    editor_window.show_message.assert_called_once_with(message)
    editor_window.add_tab.assert_not_called()


def test_no_duplicate_load_python_file_widget_file_no_longer_exists():
    """
    If the user specifies a file already loaded (but which no longer exists),
    ensure this is detected, logged and Mu doesn't crash..! See:

    https://github.com/mu-editor/mu/issues/774

    for context.
    """
    brown_script = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        "scripts",
        "contains_brown.py",
    )

    editor_window = mock.MagicMock()
    editor_window.show_message = mock.MagicMock()
    editor_window.focus_tab = mock.MagicMock()
    editor_window.add_tab = mock.MagicMock()

    missing_tab = mock.MagicMock()
    missing_tab.path = "not_a_file.py"

    editor_window.widgets = [missing_tab]

    editor_window.current_tab.path = "path"
    # Create the "editor" that'll control the "window".
    editor = mu.logic.Editor(view=editor_window)
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "/fake/path"
    editor.modes = {"python": mock_mode}
    with mock.patch("mu.logic.logger") as mock_logger:
        editor._load(brown_script)
        assert mock_logger.info.call_count == 3
        log = mock_logger.info.call_args_list[1][0][0]
        assert log == "The file not_a_file.py no longer exists."


def test_load_other_file():
    """
    If the user specifies a file supported by a Mu mode (like a .hex file) then
    ensure it's loaded and added as a tab.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(return_value="foo.hex")
    view.add_tab = mock.MagicMock()
    view.show_confirmation = mock.MagicMock()
    view.current_tab.path = "path"
    ed = mu.logic.Editor(view)
    ed.change_mode = mock.MagicMock()
    api = ["API specification"]
    file_content = "PYTHON CODE"
    mock_py = mock.MagicMock()
    mock_py.file_extensions = None
    mock_py.open_file.return_value = None
    mock_mb = mock.MagicMock()
    mock_mb.api.return_value = api
    mock_mb.workspace_dir.return_value = "/fake/path"
    mock_mb.open_file.return_value = (file_content, os.linesep)
    mock_mb.file_extensions = ["hex"]
    ed.modes = {"python": mock_py, "microbit": mock_mb}
    ed.mode = "microbit"
    with (
        mock.patch("builtins.open", mock.mock_open()),
        mock.patch("os.path.isfile", return_value=True),
    ):
        ed.load()
    assert view.get_load_path.call_count == 1
    assert view.show_confirmation.call_count == 0
    assert ed.change_mode.call_count == 0
    view.add_tab.assert_called_once_with(None, file_content, api, os.linesep)


def test_load_other_file_change_mode():
    """
    If the user specifies a file supported by a Mu mode (like a .html file)
    that is not currently active, then ensure it's loaded, added as a tab, andi
    it asks the user to change mode.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(return_value="foo.html")
    view.add_tab = mock.MagicMock()
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Ok)
    view.current_tab.path = "path"
    ed = mu.logic.Editor(view)
    ed.change_mode = mock.MagicMock()
    api = ["API specification"]
    file_content = "<html></html>"
    mock_py = mock.MagicMock()
    mock_py.open_file.return_value = None
    mock_py.api.return_value = api
    mock_py.workspace_dir.return_value = "/fake/path"
    mock_mb = mock.MagicMock()
    mock_mb.api.return_value = api
    mock_mb.workspace_dir.return_value = "/fake/path"
    mock_mb.open_file.return_value = (file_content, os.linesep)
    mock_mb.file_extensions = ["hex"]
    ed.modes = {"python": mock_py, "microbit": mock_mb}
    ed.mode = "python"
    with (
        mock.patch("builtins.open", mock.mock_open()),
        mock.patch("os.path.isfile", return_value=True),
    ):
        ed.load()
    assert view.get_load_path.call_count == 1
    assert view.show_confirmation.call_count == 1
    assert ed.change_mode.call_count == 1
    view.add_tab.assert_called_once_with(
        "foo.html", file_content, api, os.linesep
    )


def test_load_other_file_with_exception():
    """
    If the user specifies a file supported by a Mu mode (like a .hex file) try
    to open it and check it ignores it if it throws an unexpected exception.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(return_value="foo.hex")
    view.add_tab = mock.MagicMock()
    view.show_confirmation = mock.MagicMock()
    view.current_tab.path = "path"
    ed = mu.logic.Editor(view)
    ed.change_mode = mock.MagicMock()
    mock_mb = mock.MagicMock()
    mock_mb.workspace_dir.return_value = "/fake/path"
    mock_mb.open_file = mock.MagicMock(side_effect=Exception(":("))
    mock_mb.file_extensions = ["hex"]
    ed.modes = {"microbit": mock_mb}
    ed.mode = "microbit"
    mock_open = mock.mock_open()
    with (
        mock.patch("builtins.open", mock_open),
        mock.patch("os.path.isfile", return_value=True),
    ):
        ed.load()
    assert view.get_load_path.call_count == 1
    assert view.show_message.call_count == 1
    assert view.show_confirmation.call_count == 0
    assert ed.change_mode.call_count == 0
    assert view.add_tab.call_count == 0


def test_load_not_python_or_hex():
    """
    If the user tries to open a file that isn't .py or .hex then Mu should
    report a helpful message.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    with mock.patch("os.path.isfile", return_value=True):
        ed._load("unknown_filetype.foo")
    assert view.show_message.call_count == 1


def test_load_recovers_from_oserror():
    """
    If loading the file results in an OSError (for example, the user doesn't
    have permission to read the file), then a helpful message is displayed.
    """
    text = "python"
    ed = mocked_editor()
    with (
        generate_python_file(text) as filepath,
        mock.patch("mu.logic.read_and_decode", side_effect=OSError("boom")),
    ):
        ed._view.get_load_path.return_value = filepath
        ed.load()
    assert ed._view.show_message.call_count == 1


#
# When loading files Mu makes a note of the majority line-ending convention
# in use in the file. When it is saved, that convention is used.
#
def test_load_stores_newline():
    """
    When a file is loaded, its newline convention should be held on the tab
    for use when saving.
    """
    newline = "r\n"
    text = newline.join("the cat sat on the mat".split())
    editor = mocked_editor()
    with generate_python_file(text) as filepath:
        editor._view.get_load_path.return_value = filepath
        editor.load()

    editor._view.add_tab.assert_called_with(
        filepath, text, editor.modes[editor.mode].api(), "\n"
    )


def test_save_restores_newline():
    """
    When a file is saved the newline convention noted originally should
    be used.
    """
    newline = "\r\n"
    test_text = mu.logic.NEWLINE.join("the cat sat on the mat".split())
    with generate_python_file(test_text) as filepath:
        with mock.patch("mu.logic.save_and_encode") as mock_save:
            ed = mocked_editor(text=test_text, newline=newline, path=filepath)
            ed.save()
            mock_save.assert_called_with(test_text, filepath, newline)


def test_save_strips_trailing_spaces():
    """
    When a file is saved any trailing spaces should be removed from each line
    leaving any newlines intact. NB we inadvertently strip trailing newlines
    in any case via save_and_encode
    """
    words = "the cat sat on the mat".split()
    test_text = mu.logic.NEWLINE.join("%s " % w for w in words)
    stripped_text = mu.logic.NEWLINE.join(words)
    with generate_python_file(test_text) as filepath:
        mu.logic.save_and_encode(test_text, filepath)
        with open(filepath) as f:
            assert f.read() == stripped_text + "\n"


def test_load_error():
    """
    Ensure that anything else is just ignored.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(return_value="foo.py")
    view.add_tab = mock.MagicMock()
    view.current_tab.path = "path"
    ed = mu.logic.Editor(view)
    mock_open = mock.MagicMock(side_effect=FileNotFoundError())
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "/fake/path"
    ed.modes = {"python": mock_mode}
    with mock.patch("builtins.open", mock_open):
        ed.load()
    assert view.get_load_path.call_count == 1
    assert view.add_tab.call_count == 0


def test_load_sets_current_path():
    """
    When a path has been selected for loading by the OS's file selector,
    ensure that the directory containing the selected file is set as the
    self.current_path for reuse later on.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(
        return_value=os.path.join("path", "foo.py")
    )
    view.current_tab.path = os.path.join("old_path", "foo.py")
    ed = mu.logic.Editor(view)
    ed._load = mock.MagicMock()
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "/fake/path"
    mock_mode.file_extensions = ["html", "css"]
    ed.modes = {"python": mock_mode}
    ed.load()
    assert ed.current_path == os.path.abspath("path")


def test_load_no_current_path():
    """
    If there is no self.current_path the default location to look for a file
    to load is the directory containing the file currently being edited.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(
        return_value=os.path.join("path", "foo.py")
    )
    view.current_tab.path = os.path.join("old_path", "foo.py")
    ed = mu.logic.Editor(view)
    ed._load = mock.MagicMock()
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "/fake/path"
    mock_mode.file_extensions = []
    ed.modes = {"python": mock_mode}
    ed.load()
    expected = os.path.abspath("old_path")
    view.get_load_path.assert_called_once_with(
        expected, "*.py *.pyw *.PY *.PYW", allow_previous=True
    )


def test_load_no_current_path_no_current_tab():
    """
    If there is no self.current_path nor is there a current file being edited
    then the default location to look for a file to load is the current
    mode's workspace directory. This used to be the default behaviour, but now
    acts as a sensible fall-back.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(
        return_value=os.path.join("path", "foo.py")
    )
    view.current_tab = None
    ed = mu.logic.Editor(view)
    ed._load = mock.MagicMock()
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = os.path.join("fake", "path")
    mock_mode.file_extensions = []
    ed.modes = {"python": mock_mode}
    ed.load()
    expected = mock_mode.workspace_dir()
    view.get_load_path.assert_called_once_with(
        expected, "*.py *.pyw *.PY *.PYW", allow_previous=True
    )


def test_load_has_current_path_does_not_exist():
    """
    If there is a self.current_path but it doesn't exist, then use the expected
    fallback as the location to look for a file to load.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(
        return_value=os.path.join("path", "foo.py")
    )
    view.current_tab = None
    ed = mu.logic.Editor(view)
    ed._load = mock.MagicMock()
    ed.current_path = "foo"
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = os.path.join("fake", "path")
    mock_mode.file_extensions = []
    ed.modes = {"python": mock_mode}
    ed.load()
    expected = mock_mode.workspace_dir()
    view.get_load_path.assert_called_once_with(
        expected, "*.py *.pyw *.PY *.PYW", allow_previous=True
    )


def test_load_has_current_path():
    """
    If there is a self.current_path then use this as the location to look for
    a file to load.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(
        return_value=os.path.join("path", "foo.py")
    )
    view.current_tab = None
    ed = mu.logic.Editor(view)
    ed._load = mock.MagicMock()
    ed.current_path = "foo"
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = os.path.join("fake", "path")
    mock_mode.file_extensions = []
    ed.modes = {"python": mock_mode}
    with mock.patch("os.path.isdir", return_value=True):
        ed.load()
    view.get_load_path.assert_called_once_with(
        "foo", "*.py *.pyw *.PY *.PYW", allow_previous=True
    )


def test_load_has_default_path():
    """
    If there is a default_path argument then use this as the location to look
    for a file to load.
    """
    view = mock.MagicMock()
    view.get_load_path = mock.MagicMock(
        return_value=os.path.join("path", "foo.py")
    )
    view.current_tab = None
    ed = mu.logic.Editor(view)
    ed._load = mock.MagicMock()
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = os.path.join("fake", "path")
    mock_mode.file_extensions = []
    ed.modes = {"python": mock_mode}
    with mock.patch("os.path.isdir", return_value=True):
        ed.load(default_path="foo")
    view.get_load_path.assert_called_once_with(
        "foo", "*.py *.pyw *.PY *.PYW", allow_previous=False
    )


def test_get_dialog_directory_workspace_dir_exception():
    """
    If workspace_dir raises, fallback to python mode's workspace_dir.
    """
    ed = mu.logic.Editor(mock.MagicMock())
    ed.current_path = None
    ed.mode = "circuitpython"
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.side_effect = Exception("fail")
    python_mode = mock.MagicMock()
    python_mode.workspace_dir.return_value = "/python_workspace"
    ed.modes = {"circuitpython": mock_mode, "python": python_mode}
    ed._view.current_tab = None
    with mock.patch("os.path.isdir", return_value=False):
        with mock.patch("mu.logic.logger.error") as mock_error:
            result = ed.get_dialog_directory()
            assert result == "/python_workspace"
            assert mock_error.call_count == 1


def test_check_for_shadow_module_with_match():
    """
    If the name of the file in the path passed into check_for_shadow_module
    (without the .py file extension) is found in module_names then return
    True since the filename shadows that of a module found on the Python path.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    mock_mode = mock.MagicMock()
    mock_mode.module_names = set(["foo", "bar", "baz"])
    ed.modes = {"python": mock_mode}
    ed.mode = "python"
    assert ed.check_for_shadow_module("/a/long/path/with/foo.py")


def test_save_no_tab():
    """
    If there's no active tab then do nothing.
    """
    view = mock.MagicMock()
    view.current_tab = None
    ed = mu.logic.Editor(view)
    ed.save()
    # If the code fell through then the tab state would be modified.
    assert view.current_tab is None


def test_save_no_path():
    """
    If there's no path associated with the tab then request the user provide
    one.
    """
    text, path, newline = "foo", "foo.py", "\n"
    ed = mocked_editor(text=text, path=None, newline=newline)
    ed._view.get_save_path.return_value = path
    ed.check_for_shadow_module = mock.MagicMock(return_value=False)
    with mock.patch("mu.logic.save_and_encode") as mock_save:
        ed.save()
    mock_save.assert_called_with(text, path, newline)


def test_save_no_path_no_path_given():
    """
    If there's no path associated with the tab and the user cancels providing
    one, ensure the path is correctly re-set.
    """
    text, newline = "foo", "\n"
    ed = mocked_editor(text=text, path=None, newline=newline)
    ed._view.get_save_path.return_value = ""
    ed.save()
    # The path isn't the empty string returned from get_save_path.
    assert ed._view.current_tab.path is None


def test_save_path_shadows_module():
    """
    If the filename in the path shadows a module then display a warning message
    and abort.
    """
    text, newline = "foo", "\n"
    ed = mocked_editor(text=text, path=None, newline=newline)
    ed._view.get_save_path.return_value = "/a/long/path/foo.py"
    mock_mode = mock.MagicMock()
    mock_mode.module_names = set(["foo", "bar", "baz"])
    ed.modes = {"python": mock_mode}
    ed.mode = "python"
    ed.save()
    # The path isn't the empty string returned from get_save_path.
    assert ed._view.show_message.call_count == 1
    assert ed._view.current_tab.path is None


def test_save_file_with_exception():
    """
    If the file cannot be written, return an error message.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = "foo.py"
    view.current_tab.text = mock.MagicMock(return_value="foo")
    view.current_tab.setModified = mock.MagicMock(return_value=None)
    view.show_message = mock.MagicMock()
    mock_open = mock.MagicMock(side_effect=OSError())
    ed = mu.logic.Editor(view)
    with mock.patch("builtins.open", mock_open):
        ed.save()
    assert view.current_tab.setModified.call_count == 0
    assert view.show_message.call_count == 1


def test_save_file_with_encoding_error():
    """
    If Mu encounters a UnicodeEncodeError when trying to write the file,
    it should display a helpful message explaining the problem.
    """
    text, path, newline = "foo", "foo", "\n"
    ed = mocked_editor(text=text, path=path, newline=newline)
    with mock.patch("mu.logic.save_and_encode") as mock_save:
        mock_save.side_effect = UnicodeEncodeError(
            mu.logic.ENCODING, "", 0, 0, "Unable to encode"
        )
        ed.save()

    assert ed._view.current_tab.setModified.call_count == 0


def test_save_python_file():
    """
    If the path is a Python file (ending in *.py) then save it and reset the
    modified flag.
    """
    path, contents, newline = "foo.py", "foo", "\n"
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = path
    view.current_tab.text = mock.MagicMock(return_value=contents)
    view.current_tab.newline = "\n"
    view.get_save_path = mock.MagicMock(return_value=path)
    view.current_tab.setModified = mock.MagicMock(return_value=None)
    ed = mu.logic.Editor(view)
    with mock.patch("mu.logic.save_and_encode") as mock_save:
        ed.save()

    mock_save.assert_called_once_with(contents, path, newline)
    assert view.get_save_path.call_count == 0
    view.current_tab.setModified.assert_called_once_with(False)


def test_save_with_non_py_file_extension():
    """
    If the path ends in an extension, save it using the extension
    """
    text, path, newline = "foo", "foo.txt", "\n"
    ed = mocked_editor(text=text, path=path, newline=newline)
    ed._view.get_save_path.return_value = path
    with mock.patch("mu.logic.save_and_encode") as mock_save:
        ed.save()
    mock_save.assert_called_once_with(text, path, newline)
    assert ed._view.get_save_path.call_count == 0


def test_get_tab_existing_tab():
    """
    Ensure that an existing tab is returned if its path matches.
    """
    view = mock.MagicMock()
    mock_tab = mock.MagicMock()
    mock_tab.path = "foo"
    view.widgets = [mock_tab]
    ed = mu.logic.Editor(view)
    view.focus_tab.reset_mock()
    tab = ed.get_tab("foo")
    assert tab == mock_tab
    view.focus_tab.assert_called_once_with(mock_tab)


def test_get_tab_new_tab():
    """
    If the path is not represented by an existing tab, ensure it is loaded and
    the new tab is returned.
    """
    view = mock.MagicMock()
    mock_tab = mock.MagicMock()
    mock_tab.path = "foo"
    view.widgets = [mock_tab]
    ed = mu.logic.Editor(view)
    ed.direct_load = mock.MagicMock()
    tab = ed.get_tab("bar")
    ed.direct_load.assert_called_once_with("bar")
    assert tab == view.current_tab


def test_get_tab_no_path():
    """
    Any tabs with no associated path are ignored (i.e. tabs that have been
    newly created but remain unsaved).
    """
    view = mock.MagicMock()
    mock_tab = mock.MagicMock()
    mock_tab.path = None
    view.widgets = [mock_tab]
    ed = mu.logic.Editor(view)
    ed.direct_load = mock.MagicMock()
    tab = ed.get_tab("bar")
    ed.direct_load.assert_called_once_with("bar")
    assert tab == view.current_tab


def test_zoom_in():
    """
    Ensure the UI layer is zoomed in.
    """
    view = mock.MagicMock()
    view.zoom_in = mock.MagicMock(return_value=None)
    ed = mu.logic.Editor(view)
    ed.zoom_in()
    assert view.zoom_in.call_count == 1


def test_zoom_out():
    """
    Ensure the UI layer is zoomed out.
    """
    view = mock.MagicMock()
    view.zoom_out = mock.MagicMock(return_value=None)
    ed = mu.logic.Editor(view)
    ed.zoom_out()
    assert view.zoom_out.call_count == 1


def test_check_code_on():
    """
    Checking code correctly results in something the UI layer can parse.
    """
    view = mock.MagicMock()
    tab = mock.MagicMock()
    tab.has_annotations = False
    tab.path = "foo.py"
    tab.text.return_value = "import this\n"
    view.current_tab = tab
    flake = {2: {"line_no": 2, "message": "a message"}}
    pep8 = {
        2: [{"line_no": 2, "message": "another message"}],
        3: [{"line_no": 3, "message": "yet another message"}],
    }
    mock_mode = mock.MagicMock()
    mock_mode.builtins = None
    with (
        mock.patch("mu.logic.check_flake", return_value=flake),
        mock.patch("mu.logic.check_pycodestyle", return_value=pep8),
    ):
        ed = mu.logic.Editor(view)
        ed.modes = {"python": mock_mode}
        ed.check_code()
        assert tab.has_annotations is True
        view.reset_annotations.assert_called_once_with()
        view.annotate_code.assert_has_calls(
            [mock.call(flake, "error"), mock.call(pep8, "style")],
            any_order=True,
        )


def test_check_code_no_problems():
    """
    If no problems are found in the code, ensure a status message is shown to
    the user to confirm the fact. See #337
    """
    view = mock.MagicMock()
    tab = mock.MagicMock()
    tab.has_annotations = False
    tab.path = "foo.py"
    tab.text.return_value = "import this\n"
    view.current_tab = tab
    flake = {}
    pep8 = {}
    mock_mode = mock.MagicMock()
    mock_mode.builtins = None
    with (
        mock.patch("mu.logic.check_flake", return_value=flake),
        mock.patch("mu.logic.check_pycodestyle", return_value=pep8),
    ):
        ed = mu.logic.Editor(view)
        ed.show_status_message = mock.MagicMock()
        ed.modes = {"python": mock_mode}
        ed.check_code()
        assert ed.show_status_message.call_count == 1


def test_check_code_off():
    """
    If the tab already has annotations, toggle them off.
    """
    view = mock.MagicMock()
    tab = mock.MagicMock()
    tab.has_annotations = True
    view.current_tab = tab
    ed = mu.logic.Editor(view)
    ed.check_code()
    assert tab.has_annotations is False
    view.reset_annotations.assert_called_once_with()


def test_check_code_no_tab():
    """
    Checking code when there is no tab containing code aborts the process.
    """
    view = mock.MagicMock()
    view.current_tab = None
    ed = mu.logic.Editor(view)
    ed.check_code()
    assert view.annotate_code.call_count == 0


def test_check_code_not_python():
    """
    Checking code when the tab does not contain Python code aborts the process.
    """
    view = mock.MagicMock()
    view.current_tab = mock.MagicMock()
    view.current_tab.path = "foo.html"
    ed = mu.logic.Editor(view)
    ed.check_code()
    assert view.annotate_code.call_count == 0


def test_show_help():
    """
    Help should attempt to open up the user's browser and point it to the
    expected help documentation.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    with (
        mock.patch("mu.logic.webbrowser.open_new", return_value=None) as wb,
        mock.patch("mu.i18n.language_code", "en_GB"),
    ):
        ed.show_help()
        url = "https://codewith.mu/en/help/1.2"
        wb.assert_called_once_with(url)


def test_quit_modified_cancelled_from_button():
    """
    If the user quits and there's unsaved work, and they cancel the "quit" then
    do nothing.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Cancel)
    ed = mu.logic.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    with (
        mock.patch("sys.exit", return_value=None),
        mock.patch("builtins.open", mock_open),
    ):
        ed.quit()
    assert view.show_confirmation.call_count == 1
    assert mock_open.call_count == 0


def test_quit_modified_cancelled_from_event():
    """
    If the user quits and there's unsaved work, and they cancel the "quit" then
    do nothing.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Cancel)
    ed = mu.logic.Editor(view)
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with (
        mock.patch("sys.exit", return_value=None),
        mock.patch("builtins.open", mock_open),
    ):
        ed.quit(mock_event)
    assert view.show_confirmation.call_count == 1
    assert mock_event.ignore.call_count == 1
    assert mock_open.call_count == 0


def test_quit_modified_ok():
    """
    If the user quits and there's unsaved work that's ignored then proceed to
    save the session.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    ed = mu.logic.Editor(view)
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "foo/bar"
    mock_mode.get_hex_path.return_value = "foo/bar"
    mock_debug_mode = mock.MagicMock()
    mock_debug_mode.is_debugger = True
    ed.modes = {
        "python": mock_mode,
        "microbit": mock_mode,
        "debugger": mock_debug_mode,
    }
    ed.mode = "debugger"
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    #
    # FIXME TJG: not sure what the ignore functionality being mocked here is doing
    #
    mock_event.ignore = mock.MagicMock(return_value=None)
    with (
        mock.patch("sys.exit", return_value=None),
        mock.patch("mu.settings.SessionSettings.save") as mocked_save,
    ):
        ed.quit(mock_event)

    mock_debug_mode.stop.assert_called_once_with()
    assert view.show_confirmation.call_count == 1
    assert mock_event.ignore.call_count == 0
    assert mocked_save.called


def _editor_view_mock():
    """
    Return a mocked mu.interface.Window to be used as a mu.logic.Editor view
    in the test_quit_save* tests.
    """
    view = mock.MagicMock()
    view.modified = True
    view.zoom_position = 2
    view.show_confirmation = mock.MagicMock(return_value=True)
    view.x.return_value = 100
    view.y.return_value = 200
    view.width.return_value = 300
    view.height.return_value = 400
    return view


def test_quit_save_tabs_with_paths():
    """
    When saving the session, ensure those tabs with associated paths are
    logged in the session file.
    """
    view = _editor_view_mock()
    w1 = mock.MagicMock()
    w1.path = "foo.py"
    view.widgets = [w1]
    ed = mu.logic.Editor(view)
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "foo/bar"
    mock_mode.get_hex_path.return_value = "foo/bar"
    ed.modes = {"python": mock_mode, "microbit": mock_mode}

    with mock.patch.object(sys, "exit"):
        with mock.patch.object(mu.logic, "save_session") as mock_save_session:
            ed.quit()

    [session], _ = mock_save_session.call_args
    assert os.path.abspath("foo.py") in session["paths"]


def test_quit_save_theme():
    """
    When saving the session, ensure the theme is logged in the session file.
    """
    view = _editor_view_mock()
    w1 = mock.MagicMock()
    w1.path = "foo.py"
    view.widgets = [w1]
    ed = mu.logic.Editor(view)
    ed.theme = "night"
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "foo/bar"
    mock_mode.get_hex_path.return_value = "foo/bar"
    ed.modes = {"python": mock_mode, "microbit": mock_mode}

    with mock.patch.object(sys, "exit"):
        with mock.patch.object(mu.logic, "save_session") as mock_save_session:
            ed.quit()

    [session], _ = mock_save_session.call_args
    assert session["theme"] == "night"


def test_quit_save_envars():
    """
    When saving the session, ensure the user defined envars are logged in the
    session file.
    """
    view = _editor_view_mock()
    w1 = mock.MagicMock()
    w1.path = "foo.py"
    view.widgets = [w1]
    ed = mu.logic.Editor(view)
    ed.theme = "night"
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "foo/bar"
    mock_mode.get_hex_path.return_value = "foo/bar"
    ed.modes = {"python": mock_mode, "microbit": mock_mode}
    ed.envars = [["name1", "value1"], ["name2", "value2"]]

    with mock.patch.object(sys, "exit"):
        with mock.patch.object(mu.logic, "save_session") as mock_save_session:
            ed.quit()

    [session], _ = mock_save_session.call_args
    assert session["envars"] == [["name1", "value1"], ["name2", "value2"]]


def test_quit_save_zoom_level():
    """
    When saving the session, ensure the zoom level is logged in the session
    file.
    """
    view = _editor_view_mock()
    w1 = mock.MagicMock()
    w1.path = "foo.py"
    view.widgets = [w1]
    ed = mu.logic.Editor(view)
    ed.theme = "night"
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "foo/bar"
    mock_mode.get_hex_path.return_value = "foo/bar"
    ed.modes = {"python": mock_mode, "microbit": mock_mode}

    with mock.patch.object(sys, "exit"):
        with mock.patch.object(mu.logic, "save_session") as mock_save_session:
            ed.quit()

    [session], _ = mock_save_session.call_args
    #
    # FIXME: not clear where this is set. Default?
    #
    assert session["zoom_level"] == 2


def test_quit_save_window_geometry():
    """
    When saving the session, ensure the window geometry is saved in the session
    file.
    """
    view = _editor_view_mock()
    w1 = mock.MagicMock()
    w1.path = "foo.py"
    view.widgets = [w1]
    ed = mu.logic.Editor(view)
    ed.theme = "night"
    mock_mode = mock.MagicMock()
    mock_mode.workspace_dir.return_value = "foo/bar"
    mock_mode.get_hex_path.return_value = "foo/bar"
    ed.modes = {"python": mock_mode, "microbit": mock_mode}

    with mock.patch.object(sys, "exit"):
        with mock.patch.object(mu.logic, "save_session") as mock_save_session:
            ed.quit()

    [session], _ = mock_save_session.call_args
    #
    # FIXME: not clear where this is set. Default?
    #
    assert session["window"] == {"x": 100, "y": 200, "w": 300, "h": 400}


def test_quit_calls_mode_stop():
    """
    Ensure that the current mode's stop method is called.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    w1 = mock.MagicMock()
    w1.path = "foo.py"
    view.widgets = [w1]
    ed = mu.logic.Editor(view)
    ed.theme = "night"
    ed.modes = {"python": mock.MagicMock(), "microbit": mock.MagicMock()}
    ed.mode = "python"
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with (
        mock.patch("sys.exit", return_value=None),
        mock.patch("builtins.open", mock_open),
        mock.patch("mu.settings.session.save"),
    ):
        ed.quit(mock_event)
    ed.modes[ed.mode].stop.assert_called_once_with()


def test_quit_calls_sys_exit(mocked_session):
    """
    Ensure that sys.exit(0) is called.
    """
    view = mock.MagicMock()
    view.modified = True
    view.show_confirmation = mock.MagicMock(return_value=True)
    w1 = mock.MagicMock()
    w1.path = "foo.py"
    view.widgets = [w1]
    ed = mu.logic.Editor(view)
    ed.theme = "night"
    ed.modes = {"python": mock.MagicMock(), "microbit": mock.MagicMock()}
    mock_open = mock.MagicMock()
    mock_open.return_value.__enter__ = lambda s: s
    mock_open.return_value.__exit__ = mock.Mock()
    mock_open.return_value.write = mock.MagicMock()
    mock_event = mock.MagicMock()
    mock_event.ignore = mock.MagicMock(return_value=None)
    with (
        mock.patch("PyQt6.QtCore.QCoreApplication.exit", return_value=0) as ex,
        mock.patch("builtins.open", mock_open),
    ):
        ed.quit(mock_event)
    ex.assert_called_once_with(0)


def test_show_admin():
    """
    Ensure the expected admin dialog is displayed to the end user.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.modes = {"python": mock.MagicMock()}
    ed.envars = {"name": "value"}
    ed.microbit_runtime = "/foo/bar"
    settings = {
        "envars": "name=value",
        "microbit_runtime": "/foo/bar",
        "locale": "",
        "pa_instance": "www",
        "pa_token": "",
        "pa_username": "",
    }
    new_settings = {
        "envars": "name=value",
        "microbit_runtime": "/foo/bar",
        "locale": "",
        "pa_instance": "www",
        "pa_token": "fake_token",
        "pa_username": "fake_username",
    }
    view.show_admin.return_value = new_settings
    mock_open = mock.mock_open()
    with (
        mock.patch("builtins.open", mock_open),
        mock.patch("os.path.isfile", return_value=True),
    ):
        ed.show_admin()
        mock_open.assert_called_once_with(
            mu.logic.LOG_FILE, "r", encoding="utf8"
        )
        assert view.show_admin.call_count == 1
        assert view.show_admin.call_args[0][1] == settings
        assert ed.envars == {"name": "value"}
        assert ed.microbit_runtime == "/foo/bar"
        assert ed.pa_instance == "www"
        assert ed.pa_token == "fake_token"
        assert ed.pa_username == "fake_username"


def test_show_admin_missing_microbit_runtime():
    """
    Ensure the microbit_runtime result is '' and a warning message is displayed
    if the specified microbit_runtime doesn't actually exist.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.modes = {"python": mock.MagicMock()}
    ed.envars = {"name": "value"}
    ed.microbit_runtime = "/foo/bar"
    settings = {
        "envars": "name=value",
        "microbit_runtime": "/foo/bar",
        "locale": "",
        "pa_instance": "www",
        "pa_token": "",
        "pa_username": "",
    }
    new_settings = {
        "envars": "name=value",
        "microbit_runtime": "/foo/bar",
        "locale": "",
        "pa_instance": "www",
        "pa_token": "",
        "pa_username": "",
    }
    view.show_admin.return_value = new_settings
    mock_open = mock.mock_open()
    with (
        mock.patch("builtins.open", mock_open),
        mock.patch("os.path.isfile", return_value=False),
    ):
        ed.show_admin(None)
        mock_open.assert_called_once_with(
            mu.logic.LOG_FILE, "r", encoding="utf8"
        )
        assert view.show_admin.call_count == 1
        assert view.show_admin.call_args[0][1] == settings
        assert ed.envars == {"name": "value"}
        assert ed.microbit_runtime == ""
        assert view.show_message.call_count == 1


def test_show_admin_no_settings_changed():
    """
    If show_admin returns None, ensure 'No admin settings changed.' is logged.
    """
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.modes = {"python": mock.MagicMock()}
    ed.mode = "python"
    ed.envars = {"name": "value"}
    ed.microbit_runtime = "/foo/bar"
    ed.user_locale = ""
    ed.pa_username = ""
    ed.pa_token = ""
    ed.pa_instance = "www"
    view.show_admin.return_value = None
    mock_open = mock.mock_open(read_data="log content")
    with mock.patch("builtins.open", mock_open):
        with mock.patch("mu.logic.logger.info") as mock_logger_info:
            ed.show_admin()
            mock_logger_info.assert_called_with("No admin settings changed.")


def test_select_mode():
    """
    It's possible to select and update to a new mode.
    """
    view = mock.MagicMock()
    view.select_mode.return_value = "foo"
    mode = mock.MagicMock()
    mode.is_debugger = False
    ed = mu.logic.Editor(view)
    ed.modes = {"python": mode}
    ed.change_mode = mock.MagicMock()
    ed.select_mode(None)
    assert view.select_mode.call_count == 1
    ed.change_mode.assert_called_once_with("foo")


def test_select_mode_debug_mode():
    """
    It's NOT possible to select and update to a new mode if you're in debug
    mode.
    """
    view = mock.MagicMock()
    mode = mock.MagicMock()
    mode.debugger = True
    ed = mu.logic.Editor(view)
    ed.modes = {"debugger": mode}
    ed.mode = "debugger"
    ed.change_mode = mock.MagicMock()
    ed.select_mode(None)
    assert ed.mode == "debugger"
    assert ed.change_mode.call_count == 0


def test_change_mode():
    """
    It should be possible to change modes in the expected fashion (buttons get
    correctly connected to event handlers).
    """
    view = mock.MagicMock()
    mock_button_bar = mock.MagicMock()
    view.button_bar = mock_button_bar
    view.change_mode = mock.MagicMock()
    ed = mu.logic.Editor(view)
    old_mode = mock.MagicMock()
    old_mode.save_timeout = 5
    old_mode.actions.return_value = [
        {"name": "name", "handler": "handler", "shortcut": "Ctrl+X"}
    ]
    mode = mock.MagicMock()
    mode.save_timeout = 5
    mode.name = "Python"
    mode.actions.return_value = [
        {"name": "name", "handler": "handler", "shortcut": "Ctrl+X"}
    ]
    ed.modes = {"microbit": old_mode, "python": mode}
    ed.mode = "microbit"
    ed.change_mode("python")
    # Check the old mode is closed properly.
    old_mode.remove_repl.assert_called_once_with()
    old_mode.remove_fs.assert_called_once_with()
    old_mode.remove_plotter.assert_called_once_with()
    # Check the new mode is set up correctly.
    assert ed.mode == "python"
    view.change_mode.assert_called_once_with(mode)
    assert mock_button_bar.connect.call_count == 12
    view.status_bar.set_mode.assert_called_once_with("Python")
    view.set_timer.assert_called_once_with(5, ed.autosave)


def test_change_mode_no_timer():
    """
    It should be possible to change modes in the expected fashion (buttons get
    correctly connected to event handlers).
    """
    view = mock.MagicMock()
    mock_button_bar = mock.MagicMock()
    view.button_bar = mock_button_bar
    view.change_mode = mock.MagicMock()
    ed = mu.logic.Editor(view)
    mode = mock.MagicMock()
    mode.save_timeout = 0
    mode.name = "Python"
    mode.actions.return_value = [
        {"name": "name", "handler": "handler", "shortcut": "Ctrl+X"}
    ]
    ed.modes = {"python": mode}
    ed.change_mode("python")
    assert ed.mode == "python"
    view.change_mode.assert_called_once_with(mode)
    assert mock_button_bar.connect.call_count == 12
    view.status_bar.set_mode.assert_called_once_with("Python")
    view.stop_timer.assert_called_once_with()


def test_change_mode_reset_breakpoints():
    """
    When changing modes, if the new mode does NOT require a debugger, then
    breakpoints should be reset.
    """
    view = mock.MagicMock()
    mock_tab = mock.MagicMock()
    mock_tab.breakpoint_handles = set([1, 2, 3])
    view.widgets = [mock_tab]
    ed = mu.logic.Editor(view)
    mode = mock.MagicMock()
    mode.has_debugger = False
    mode.is_debugger = False
    mode.save_timeout = 5
    ed.modes = {"microbit": mode, "debug": mock.MagicMock()}
    ed.mode = "debug"
    ed.change_mode("microbit")
    assert ed.mode == "microbit"
    assert mock_tab.breakpoint_handles == set()
    mock_tab.reset_annotations.assert_called_once_with()


def test_change_mode_workspace_dir_exception():
    """
    Check that any mode.workspace_dir() raising an exception doesn't crash Mu,
    but uses Python mode's workspace_dir as a default.
    """
    ed = mu.logic.Editor(mock.MagicMock())
    mode = mock.MagicMock()
    mode.save_timeout = 0
    mode.workspace_dir = mock.MagicMock(side_effect=ValueError("Some error."))
    python_mode = mock.MagicMock()
    ed.modes = {
        "circuitpython": mode,
        "python": python_mode,
        "debug": mock.MagicMock(),
    }
    ed.mode = "debug"
    with mock.patch("mu.logic.logger.error") as mock_error:
        ed.change_mode("circuitpython")
        assert mock_error.call_count == 1
    assert ed.mode == "circuitpython"
    python_mode.workspace_dir.assert_called_once_with()


def test_autosave():
    """
    Ensure the autosave callback does the expected things to the tabs.
    """
    view = mock.MagicMock()
    view.modified = True
    mock_tab = mock.MagicMock()
    mock_tab.path = "foo"
    mock_tab.isModified.return_value = True
    view.widgets = [mock_tab]
    ed = mu.logic.Editor(view)
    ed.save_tab_to_file = mock.MagicMock()
    ed.autosave()
    ed.save_tab_to_file.assert_called_once_with(
        mock_tab, show_error_messages=False
    )


def test_check_usb(microbit_com1):
    """
    Ensure the check_usb callback actually checks for connected USB devices.
    """
    mode_py = mock.MagicMock()
    mode_py.name = "Python3"
    mode_py.runner = None
    mode_py.find_devices.return_value = []
    mode_mb = mock.MagicMock()
    mode_mb.name = "BBC micro:bit"
    mode_mb.find_devices.return_value = [microbit_com1]
    modes = {"microbit": mode_mb, "python": mode_py}
    device_list = mu.logic.DeviceList(modes)
    device_list.device_connected = mock.MagicMock()
    device_list.check_usb()
    device_list.device_connected.emit.assert_called_with(microbit_com1)


def test_check_usb_remove_disconnected_devices(microbit_com1):
    """
    Ensure that if a device is no longer connected, it is removed from
    the set of connected devices.
    """
    # No modes, so no devices should be detected
    modes = {}
    device_list = mu.logic.DeviceList(modes)
    device_list.add_device(microbit_com1)
    device_list.check_usb()
    assert len(device_list) == 0


def test_ask_to_change_mode_confirm():
    """
    Ensure the ask_to_change_mode calls change_mode, if user confirms.
    """
    view = mock.MagicMock()
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Ok)
    ed = mu.logic.Editor(view)
    ed.change_mode = mock.MagicMock()
    mode_py = mock.MagicMock()
    mode_py.name = "Python3"
    mode_py.runner = None
    mode_mb = mock.MagicMock()
    mode_mb.name = "BBC micro:bit"
    ed.modes = {"microbit": mode_mb, "python": mode_py}
    ed.ask_to_change_mode("microbit", "python", "New device detected")
    assert view.show_confirmation.called
    ed.change_mode.assert_called_once_with("microbit")


def test_ask_to_change_mode_cancel(adafruit_feather):
    """
    Ensure the ask_to_change_mode doesn't change mode if confirmation cancelled
    by user.
    """
    view = mock.MagicMock()
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Cancel)
    ed = mu.logic.Editor(view)
    ed.change_mode = mock.MagicMock()
    mode_py = mock.MagicMock()
    mode_py.name = "Python3"
    mode_py.runner = None
    mode_cp = mock.MagicMock()
    mode_cp.name = "CircuitPlayground"
    ed.modes = {"circuitplayground": mode_cp, "python": mode_py}
    ed.ask_to_change_mode(mode_cp, mode_py, "New device detected")
    assert view.show_confirmation.called
    ed.change_mode.assert_not_called()


def test_ask_to_change_mode_already_in_mode(microbit_com1):
    """
    Ensure the ask_to_change_mode doesn't ask to change mode if already
    selected.
    """
    view = mock.MagicMock()
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Ok)
    ed = mu.logic.Editor(view)
    ed.change_mode = mock.MagicMock()
    mode_mb = mock.MagicMock()
    mode_mb.name = "BBC micro:bit"
    mode_mb.find_devices.return_value = [microbit_com1]
    mode_cp = mock.MagicMock()
    mode_cp.find_devices.return_value = []
    ed.modes = {"microbit": mode_mb, "circuitplayground": mode_cp}
    ed.mode = "microbit"
    ed.show_status_message = mock.MagicMock()
    ed.ask_to_change_mode(mode_mb, mode_mb, "New device detected")
    view.show_confirmation.assert_not_called()
    ed.change_mode.assert_not_called()


def test_ask_to_change_mode_currently_running_code(microbit_com1):
    """
    Ensure the ask_to_check_mode doesn't ask to change mode if the current mode
    is running code.
    """
    view = mock.MagicMock()
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Ok)
    ed = mu.logic.Editor(view)
    ed.change_mode = mock.MagicMock()
    mode_py = mock.MagicMock()
    mode_py.name = "Python3"
    mode_py.runner = True
    mode_py.find_device.return_value = []
    mode_mb = mock.MagicMock()
    mode_mb.name = "BBC micro:bit"
    mode_mb.find_devices.return_value = [microbit_com1]
    ed.modes = {"microbit": mode_mb, "python": mode_py}
    ed.show_status_message = mock.MagicMock()
    ed.ask_to_change_mode(mode_mb, mode_py, "New device detected")
    view.show_confirmation.assert_not_called()
    ed.change_mode.assert_not_called()


def test_ask_to_change_mode_when_selecting_mode_is_silent(adafruit_feather):
    """
    Ensure ask_to_change_mode doesn't ask to change mode if the user has
    the mode selection dialog active (indicated by the selecting_mode flag).
    """
    view = mock.MagicMock()
    view.show_confirmation = mock.MagicMock(return_value=QMessageBox.Cancel)
    ed = mu.logic.Editor(view)
    ed.change_mode = mock.MagicMock()
    mode_py = mock.MagicMock()
    mode_py.name = "Python3"
    mode_py.runner = None
    mode_py.find_devices.return_value = []
    mode_cp = mock.MagicMock()
    mode_cp.name = "CircuitPlayground"
    mode_cp.find_devices.return_value = [adafruit_feather]
    ed.modes = {"circuitplayground": mode_cp, "python": mode_py}
    ed.selecting_mode = True
    ed.ask_to_change_mode(mode_cp, mode_py, "New device detected")
    assert view.show_confirmation.call_count == 0
    ed.change_mode.assert_not_called()


def test_device_changed(microbit_com1, adafruit_feather):
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.ask_to_change_mode = mock.MagicMock()
    ed.device_changed(adafruit_feather)
    ed.ask_to_change_mode.assert_called_once_with(
        "circuitpython",
        "CircuitPython",
        "Detected new Adafruit Feather device.",
    )
    assert ed.current_device == adafruit_feather
    ed.device_changed(microbit_com1)
    assert ed.ask_to_change_mode.call_count == 2
    assert ed.current_device == microbit_com1


def test_show_status_message():
    """
    Ensure the method calls the status_bar in the view layer.
    """
    msg = "Hello, World!"
    view = mock.MagicMock()
    ed = mu.logic.Editor(view)
    ed.show_status_message(msg, 8)
    view.status_bar.set_message.assert_called_once_with(msg, 8000)


def test_debug_toggle_breakpoint_as_debugger():
    """
    If a breakpoint is toggled in debug mode, pass it to the toggle_breakpoint
    method in the debug client.
    """
    view = mock.MagicMock()
    view.current_tab.text.return_value = 'print("Hello")'
    ed = mu.logic.Editor(view)
    mock_debugger = mock.MagicMock()
    mock_debugger.has_debugger = False
    mock_debugger.is_debugger = True
    ed.modes = {"debugger": mock_debugger}
    ed.mode = "debugger"
    ed.debug_toggle_breakpoint(1, 10, False)
    mock_debugger.toggle_breakpoint.assert_called_once_with(
        10, view.current_tab
    )


def test_debug_toggle_breakpoint_on():
    """
    Toggle the breakpoint on when not in debug mode by tracking it in the
    tab.breakpoint_handles set.
    """
    view = mock.MagicMock()
    view.current_tab.breakpoint_handles = set()
    view.current_tab.markersAtLine.return_value = False
    view.current_tab.markerAdd.return_value = 999  # the tracked marker handle.
    ed = mu.logic.Editor(view)
    mock_debugger = mock.MagicMock()
    mock_debugger.has_debugger = True
    mock_debugger.is_debugger = False
    ed.modes = {"python": mock_debugger}
    ed.mode = "python"
    ed.debug_toggle_breakpoint(1, 10, False)
    view.current_tab.markerAdd.assert_called_once_with(
        10, view.current_tab.BREAKPOINT_MARKER
    )
    assert 999 in view.current_tab.breakpoint_handles


def test_debug_toggle_breakpoint_off():
    """
    Toggle the breakpoint off when not in debug mode by tracking it in the
    tab.breakpoint_handles set.
    """
    view = mock.MagicMock()
    view.current_tab.breakpoint_handles = set([10])
    ed = mu.logic.Editor(view)
    mock_debugger = mock.MagicMock()
    mock_debugger.has_debugger = True
    mock_debugger.is_debugger = False
    ed.modes = {"python": mock_debugger}
    ed.mode = "python"
    ed.debug_toggle_breakpoint(1, 10, False)
    view.current_tab.markerDelete.assert_called_once_with(10, -1)


def test_rename_tab_no_tab_id():
    """
    If no tab id is supplied (i.e. this method was triggered by the shortcut
    instead of the double-click event), then use the tab currently in focus.
    """
    view = mock.MagicMock()
    view.get_save_path.return_value = "foo"
    mock_tab = mock.MagicMock()
    mock_tab.path = "old.py"
    view.current_tab = mock_tab
    ed = mu.logic.Editor(view)
    ed.save = mock.MagicMock()
    ed.check_for_shadow_module = mock.MagicMock(return_value=False)
    ed.rename_tab()
    view.get_save_path.assert_called_once_with("old.py")
    assert mock_tab.path == "foo.py"
    ed.save.assert_called_once_with()


def test_rename_tab():
    """
    If there's a tab id, the function being tested is reacting to a double-tap
    so make sure the expected tab is grabbed from the view.
    """
    view = mock.MagicMock()
    view.get_save_path.return_value = "foo"
    mock_tab = mock.MagicMock()
    mock_tab.path = "old.py"
    view.tabs.widget.return_value = mock_tab
    ed = mu.logic.Editor(view)
    ed.save = mock.MagicMock()
    ed.check_for_shadow_module = mock.MagicMock(return_value=False)
    ed.rename_tab(1)
    view.get_save_path.assert_called_once_with("old.py")
    view.tabs.widget.assert_called_once_with(1)
    assert mock_tab.path == "foo.py"
    ed.save.assert_called_once_with()


def test_rename_tab_with_shadow_module():
    """
    If the user attempts to rename the tab to a filename which shadows a
    Python module, then a warning should appear and the process aborted.
    """
    view = mock.MagicMock()
    view.get_save_path.return_value = "foo"
    mock_tab = mock.MagicMock()
    mock_tab.path = "old.py"
    view.tabs.widget.return_value = mock_tab
    ed = mu.logic.Editor(view)
    ed.save = mock.MagicMock()
    ed.check_for_shadow_module = mock.MagicMock(return_value=True)
    ed.rename_tab(1)
    view.get_save_path.assert_called_once_with("old.py")
    view.tabs.widget.assert_called_once_with(1)
    assert view.show_message.call_count == 1
    assert mock_tab.path == "old.py"
    assert ed.save.call_count == 0


def test_rename_tab_avoid_duplicating_other_tab_name():
    """
    If the user attempts to rename the tab to a filename used by another tab
    then show an error message and don't rename anything.
    """
    view = mock.MagicMock()
    view.get_save_path.return_value = "foo"
    mock_other_tab = mock.MagicMock()
    mock_other_tab.path = "foo.py"
    view.widgets = [mock_other_tab]
    mock_tab = mock.MagicMock()
    mock_tab.path = "old.py"
    view.tabs.widget.return_value = mock_tab
    ed = mu.logic.Editor(view)
    ed.check_for_shadow_module = mock.MagicMock(return_value=False)
    ed.rename_tab(1)
    view.show_message.assert_called_once_with(
        "Could not rename file.",
        "A file of that name is already open in Mu.",
    )
    assert mock_tab.path == "old.py"


def test_logic_independent_import_logic():
    """
    It should be possible to import the logic and app
    modules from the mu package independently of each
    other.
    """
    subprocess.run([sys.executable, "-c", "from mu import logic"], check=True)


def test_logic_independent_import_app():
    """
    It should be possible to import the logic and app
    modules from the mu package independently of each
    other.
    """
    subprocess.run([sys.executable, "-c", "from mu import app"], check=True)


#
# Tests for newline detection
# Mu should detect the majority newline convention
# in a loaded file and use that convention when writing
# the file out again. Internally all newlines are MU_NEWLINE
#


def test_read_newline_no_text():
    """If the file being loaded is empty, use the platform default newline"""
    with generate_python_file() as filepath:
        text, newline = mu.logic.read_and_decode(filepath)
        assert text.count("\r\n") == 0
        assert newline == os.linesep


def test_read_newline_all_unix():
    """If the file being loaded has only the Unix convention, use that"""
    with generate_python_file("abc\ndef") as filepath:
        text, newline = mu.logic.read_and_decode(filepath)
        assert text.count("\r\n") == 0
        assert newline == "\n"


def test_read_newline_all_windows():
    """If the file being loaded has only the Windows convention, use that"""
    with generate_python_file("abc\r\ndef") as filepath:
        text, newline = mu.logic.read_and_decode(filepath)
        assert text.count("\r\n") == 0
        assert newline == "\r\n"


def test_read_newline_most_unix():
    """If the file being loaded has mostly the Unix convention, use that"""
    with generate_python_file("\nabc\r\ndef\n") as filepath:
        text, newline = mu.logic.read_and_decode(filepath)
        assert text.count("\r\n") == 0
        assert newline == "\n"


def test_read_newline_most_windows():
    """If the file being loaded has mostly the Windows convention, use that"""
    with generate_python_file("\r\nabc\ndef\r\n") as filepath:
        text, newline = mu.logic.read_and_decode(filepath)
        assert text.count("\r\n") == 0
        assert newline == "\r\n"


def test_read_newline_equal_match():
    """If the file being loaded has an equal number of Windows and
    Unix newlines, use the platform default
    """
    with generate_python_file("\r\nabc\ndef") as filepath:
        text, newline = mu.logic.read_and_decode(filepath)
        assert text.count("\r\n") == 0
        assert newline == os.linesep


#
# When writing Mu should honour the line-ending convention found inbound
#
def test_write_newline_to_unix():
    """If the file had Unix newlines it should be saved with Unix newlines

    (In principle this check is unnecessary as Unix newlines are currently
    the Mu internal default; but we leave it here in case that situation
    changes)
    """
    with generate_python_file() as filepath:
        test_string = "\r\n".join("the cat sat on the mat".split())
        mu.logic.save_and_encode(test_string, filepath, "\n")
        with open(filepath, newline="") as f:
            text = f.read()
            assert text.count("\r\n") == 0
            assert text.count("\n") == test_string.count("\r\n") + 1


def test_write_newline_to_windows():
    """If the file had Windows newlines it should be saved with Windows
    newlines
    """
    with generate_python_file() as filepath:
        test_string = "\n".join("the cat sat on the mat".split())
        mu.logic.save_and_encode(test_string, filepath, "\r\n")
        with open(filepath, newline="") as f:
            text = f.read()
            assert len(re.findall("[^\r]\n", text)) == 0
            assert text.count("\r\n") == test_string.count("\n") + 1


#
# Generate a Unicode test string which includes all the usual
# 7-bit characters but also an 8th-bit range which tends to
# trip things up between encodings
#
BYTES_TEST_STRING = bytes(range(0x20, 0x80)) + bytes(range(0xA0, 0xFF))
UNICODE_TEST_STRING = BYTES_TEST_STRING.decode("iso-8859-1")


#
# Tests for encoding detection
# Mu should detect:
# - BOM (UTF8/16)
# - Encoding cooke, eg # -*- coding: utf-8 -*-
# - fallback to the platform default (locale.getpreferredencoding())
#
def test_read_utf8bom():
    """Successfully decode from utf-8 encoded with BOM"""
    with generate_python_file() as filepath:
        with open(filepath, "w", encoding="utf-8-sig") as f:
            f.write(UNICODE_TEST_STRING)
        text, _ = mu.logic.read_and_decode(filepath)
        assert text == UNICODE_TEST_STRING


def test_read_utf16bebom():
    """Successfully decode from utf-16 BE encoded with BOM"""
    with generate_python_file() as filepath:
        with open(filepath, "wb") as f:
            f.write(codecs.BOM_UTF16_BE)
            f.write(UNICODE_TEST_STRING.encode("utf-16-be"))
        text, _ = mu.logic.read_and_decode(filepath)
        assert text == UNICODE_TEST_STRING


def test_read_utf16lebom():
    """Successfully decode from utf-16 LE encoded with BOM"""
    with generate_python_file() as filepath:
        with open(filepath, "wb") as f:
            f.write(codecs.BOM_UTF16_LE)
            f.write(UNICODE_TEST_STRING.encode("utf-16-le"))
        text, _ = mu.logic.read_and_decode(filepath)
        assert text == UNICODE_TEST_STRING


def test_read_encoding_cookie():
    """Successfully decode from iso-8859-1 with an encoding cookie"""
    encoding_cookie = ENCODING_COOKIE.replace(mu.logic.ENCODING, "iso-8859-1")
    test_string = encoding_cookie + UNICODE_TEST_STRING
    with generate_python_file() as filepath:
        with open(filepath, "wb") as f:
            f.write(test_string.encode("iso-8859-1"))
        text, _ = mu.logic.read_and_decode(filepath)
        assert text == test_string


def test_read_encoding_mu_default():
    """Successfully decode from the mu default"""
    test_string = UNICODE_TEST_STRING.encode(mu.logic.ENCODING)
    with generate_python_file() as filepath:
        with open(filepath, "wb") as f:
            f.write(test_string)
        text, _ = mu.logic.read_and_decode(filepath)
        assert text == UNICODE_TEST_STRING


def test_read_encoding_default():
    """Successfully decode from the default locale"""
    test_string = UNICODE_TEST_STRING.encode(locale.getpreferredencoding())
    with generate_python_file() as filepath:
        with open(filepath, "wb") as f:
            f.write(test_string)
        text, _ = mu.logic.read_and_decode(filepath)
        assert text == UNICODE_TEST_STRING


def test_read_encoding_unsuccessful():
    """Fail to decode encoded text"""
    #
    # Have to work quite hard to produce text which will definitely
    # fail to decode since UTF-8 and cp1252 (the default on this
    # computer) will, between them, decode nearly anything!
    #
    with generate_python_file() as filepath:
        with open(filepath, "wb") as f:
            f.write(codecs.BOM_UTF8)
            f.write(b"\xd8\x00")
        with pytest.raises(UnicodeDecodeError):
            text, _ = mu.logic.read_and_decode(filepath)


#
# When writing, if the text has an encoding cookie, then that encoding
# should be used. Otherwise, UTF-8 should be used and no encoding cookie
# added
#
def test_write_encoding_cookie_no_cookie():
    """If the text has no cookie of its own utf-8 will be used
    when saving and no cookie added
    """
    test_string = UNICODE_TEST_STRING
    with generate_python_file() as filepath:
        mu.logic.save_and_encode(test_string, filepath)
        with open(filepath, encoding=mu.logic.ENCODING) as f:
            for line in f:
                assert line == test_string + "\n"
                break


def test_write_encoding_cookie_existing_cookie():
    """If the text has a encoding cookie of its own then that encoding will
    be used when saving and no change made to the cookie
    """
    encoding = "iso-8859-1"
    cookie = ENCODING_COOKIE.replace(mu.logic.ENCODING, encoding)
    test_string = cookie + UNICODE_TEST_STRING
    with generate_python_file() as filepath:
        mu.logic.save_and_encode(test_string, filepath)
        with open(filepath, encoding=encoding) as f:
            assert next(f) == cookie
            assert next(f) == UNICODE_TEST_STRING + "\n"


def test_write_invalid_codec():
    """If an encoding cookie is present but specifies an unknown codec,
    utf-8 will be used instead
    """
    encoding = "INVALID"
    cookie = ENCODING_COOKIE.replace(mu.logic.ENCODING, encoding)
    test_string = cookie + UNICODE_TEST_STRING
    with generate_python_file() as filepath:
        mu.logic.save_and_encode(test_string, filepath)
        with open(filepath, encoding=mu.logic.ENCODING) as f:
            assert next(f) == cookie
            assert next(f) == UNICODE_TEST_STRING + "\n"


def test_handle_open_file():
    """
    Ensure on_open_file event handler fires as expected with the editor's
    direct_load when the view's open_file signal is emitted.
    """

    class Dummy(QObject):
        open_file = pyqtSignal(str)

    view = Dummy()
    edit = mu.logic.Editor(view)
    m = mock.MagicMock()
    edit.direct_load = m
    view.open_file.emit("/test/path.py")
    m.assert_called_once_with("/test/path.py")


def test_load_cli():
    """
    Ensure loading paths specified from the command line works as expected.
    """
    mock_view = mock.MagicMock()
    ed = mu.logic.Editor(mock_view)
    m = mock.MagicMock()
    ed.direct_load = m
    ed.load_cli(["test.py"])
    m.assert_called_once_with(os.path.abspath("test.py"))

    m = mock.MagicMock()
    ed.direct_load = m
    ed.load_cli([5])
    assert m.call_count == 0


def test_abspath():
    """
    Ensure a set of unique absolute paths is returned, given a list of
    arbitrary paths.
    """
    ed = mu.logic.Editor(mock.MagicMock())
    paths = ["foo", "bar", "bar"]
    result = ed._abspath(paths)
    assert len(result) == 2
    assert os.path.abspath("foo") in result
    assert os.path.abspath("bar") in result


def test_abspath_fail():
    """
    If given a problematic arbitrary path, _abspath will log the problem but
    continue to process the "good" paths.
    """
    ed = mu.logic.Editor(mock.MagicMock())
    paths = ["foo", "bar", 5, "bar"]
    with mock.patch("mu.logic.logger.error") as mock_error:
        result = ed._abspath(paths)
        assert mock_error.call_count == 1
    assert len(result) == 2
    assert os.path.abspath("foo") in result
    assert os.path.abspath("bar") in result


def test_find_replace_cancelled():
    """
    If the activated find/replace dialog is cancelled, no status message is
    displayed.
    """
    mock_view = mock.MagicMock()
    mock_view.show_find_replace.return_value = False
    ed = mu.logic.Editor(mock_view)
    ed.show_status_message = mock.MagicMock()
    ed.find_replace()
    assert ed.show_status_message.call_count == 0


def test_find_replace_no_find():
    """
    If the user fails to supply something to find, display a modal warning
    message to explain the problem.
    """
    mock_view = mock.MagicMock()
    mock_view.show_find_replace.return_value = ("", "", False)
    ed = mu.logic.Editor(mock_view)
    ed.show_message = mock.MagicMock()
    ed.find_replace()
    msg = "You must provide something to find."
    info = "Please try again, this time with something in the find box."
    mock_view.show_message.assert_called_once_with(msg, info)


def test_find_again_no_find():
    """
    If the user fails to supply something to find again (forward or backward),
    display a modal warning message to explain the problem.
    """
    mock_view = mock.MagicMock()
    ed = mu.logic.Editor(mock_view)
    ed.find = False
    ed.show_message = mock.MagicMock()
    ed.find_again()
    msg = "You must provide something to find."
    info = "Please try again, this time with something in the find box."
    mock_view.show_message.assert_called_once_with(msg, info)
    ed.find_again_backward(forward=False)
    assert mock_view.show_message.call_count == 2


def test_find_replace_find_matched():
    """
    If the user just supplies a find target and it is matched in the code then
    the expected status message should be shown.
    """
    mock_view = mock.MagicMock()
    mock_view.show_find_replace.return_value = ("foo", "", False)
    mock_view.highlight_text.return_value = True
    ed = mu.logic.Editor(mock_view)
    ed.show_status_message = mock.MagicMock()
    ed.find_replace()
    mock_view.highlight_text.assert_called_once_with("foo")
    assert ed.find == "foo"
    assert ed.replace == ""
    assert ed.global_replace is False
    ed.show_status_message.assert_called_once_with(
        'Highlighting matches for "foo".'
    )


def test_find_again_find_matched():
    """
    If the user supplies a find target to find again (forward or backward) and
    it is matched in the code then the expected status message should be
    shown.
    """
    mock_view = mock.MagicMock()
    mock_view.highlight_text.return_value = True
    ed = mu.logic.Editor(mock_view)
    ed.show_status_message = mock.MagicMock()
    ed.find = "foo"
    ed.find_again()
    mock_view.highlight_text.assert_called_once_with("foo", True)
    assert ed.find == "foo"
    assert ed.replace == ""
    assert ed.global_replace is False
    ed.show_status_message.assert_called_once_with(
        'Highlighting matches for "foo".'
    )
    ed.find_again_backward()
    assert ed.show_status_message.call_count == 2


def test_find_replace_find_unmatched():
    """
    If the user just supplies a find target and it is UN-matched in the code
    then the expected status message should be shown.
    """
    mock_view = mock.MagicMock()
    mock_view.show_find_replace.return_value = ("foo", "", False)
    mock_view.highlight_text.return_value = False
    ed = mu.logic.Editor(mock_view)
    ed.show_status_message = mock.MagicMock()
    ed.find_replace()
    ed.show_status_message.assert_called_once_with('Could not find "foo".')


def test_find_again_find_unmatched():
    """
    If the user supplies a find target to find_again or find_again_backward
    and it is UN-matched in the code then the expected status message should
    be shown.
    """
    mock_view = mock.MagicMock()
    mock_view.highlight_text.return_value = False
    ed = mu.logic.Editor(mock_view)
    ed.find = "foo"
    ed.show_status_message = mock.MagicMock()
    ed.find_again()
    ed.show_status_message.assert_called_once_with('Could not find "foo".')
    ed.find_again_backward()
    ed.show_status_message.assert_called_with('Could not find "foo".')
    assert ed.show_status_message.call_count == 2


def test_find_replace_replace_no_match():
    """
    If the user supplies both a find and replace target and the find target is
    UN-matched in the code, then the expected status message should be shown.
    """
    mock_view = mock.MagicMock()
    mock_view.show_find_replace.return_value = ("foo", "bar", False)
    mock_view.replace_text.return_value = 0
    ed = mu.logic.Editor(mock_view)
    ed.show_status_message = mock.MagicMock()
    ed.find_replace()
    assert ed.find == "foo"
    assert ed.replace == "bar"
    assert ed.global_replace is False
    mock_view.replace_text.assert_called_once_with("foo", "bar", False)
    ed.show_status_message.assert_called_once_with('Could not find "foo".')


def test_find_replace_replace_single_match():
    """
    If the user supplies both a find and replace target and the find target is
    matched once in the code, then the expected status message should be shown.
    """
    mock_view = mock.MagicMock()
    mock_view.show_find_replace.return_value = ("foo", "bar", False)
    mock_view.replace_text.return_value = 1
    ed = mu.logic.Editor(mock_view)
    ed.show_status_message = mock.MagicMock()
    ed.find_replace()
    assert ed.find == "foo"
    assert ed.replace == "bar"
    assert ed.global_replace is False
    mock_view.replace_text.assert_called_once_with("foo", "bar", False)
    ed.show_status_message.assert_called_once_with(
        'Replaced "foo" with "bar".'
    )


def test_find_replace_replace_multi_match():
    """
    If the user supplies both a find and replace target and the find target is
    matched many times in the code, then the expected status message should be
    shown.
    """
    mock_view = mock.MagicMock()
    mock_view.show_find_replace.return_value = ("foo", "bar", True)
    mock_view.replace_text.return_value = 4
    ed = mu.logic.Editor(mock_view)
    ed.show_status_message = mock.MagicMock()
    ed.find_replace()
    assert ed.find == "foo"
    assert ed.replace == "bar"
    assert ed.global_replace is True
    mock_view.replace_text.assert_called_once_with("foo", "bar", True)
    ed.show_status_message.assert_called_once_with(
        'Replaced 4 matches of "foo" with "bar".'
    )


def test_toggle_comments():
    """
    Ensure the method in the view for toggling comments on and off is called.
    """
    mock_view = mock.MagicMock()
    ed = mu.logic.Editor(mock_view)
    ed.toggle_comments()
    mock_view.toggle_comments.assert_called_once_with()


def test_tidy_code_no_tab():
    """
    If there's no current tab ensure black isn't called.
    """
    mock_view = mock.MagicMock()
    mock_view.current_tab = None
    ed = mu.logic.Editor(mock_view)
    ed.show_status_message = mock.MagicMock()
    ed.tidy_code()
    assert ed.show_status_message.call_count == 0


def test_tidy_code_not_python():
    """
    If the current tab doesn't contain Python, abort.
    """
    mock_view = mock.MagicMock()
    mock_view.current_tab = mock.MagicMock()
    mock_view.current_tab.path = "foo.html"
    ed = mu.logic.Editor(mock_view)
    ed.show_status_message = mock.MagicMock()
    ed.tidy_code()
    assert ed.show_status_message.call_count == 0


def test_tidy_code_valid_python():
    """
    Ensure the "good case" works as expected (the code is reformatted and Mu
    shows a status message to confirm so).
    """
    mock_view = mock.MagicMock()
    mock_view.current_tab.text.return_value = "print('hello')"
    ed = mu.logic.Editor(mock_view)
    ed.show_status_message = mock.MagicMock()
    ed.tidy_code()
    tab = mock_view.current_tab
    tab.SendScintilla.assert_called_once_with(
        tab.SCI_SETTEXT, b'print("hello")\n'
    )
    assert ed.show_status_message.call_count == 1


def test_tidy_code_invalid_python():
    """
    If the code is incorrectly formatted so black can't do its thing, ensure
    that a message is shown to the user to say so.
    """
    mock_view = mock.MagicMock()
    mock_view.current_tab.text.return_value = "print('hello'"
    ed = mu.logic.Editor(mock_view)
    ed.tidy_code()
    assert mock_view.show_message.call_count == 1


def test_check_tidy_check_line_too_long():
    """
    Check we detect, then correct, lines longer than MAX_LINE_LENGTH.
    """
    mock_view = mock.MagicMock()
    # a simple to format list running 94 characters long plus newline
    long_list = "[{}{}]\n".format(*("(1, 2), " * 10, '"0123456789"'))
    tab = mock_view.current_tab
    tab.text.return_value = long_list
    ed = mu.logic.Editor(mock_view)
    too_long = mu.logic.check_pycodestyle(tab.text.return_value)
    assert len(too_long) == 1  # One issue found: line too long
    ed.tidy_code()
    called_with = tab.SendScintilla.call_args[0][1].decode()
    tab.text.return_value = called_with
    ok = mu.logic.check_pycodestyle(tab.text.return_value)
    assert len(ok) == 0  # No issues

    assert (
        tab.text.return_value
        == """[
    (1, 2),
    (1, 2),
    (1, 2),
    (1, 2),
    (1, 2),
    (1, 2),
    (1, 2),
    (1, 2),
    (1, 2),
    (1, 2),
    "0123456789",
]
"""
    )


def test_check_tidy_check_short_line():
    """
    Check that Cidy and Check leave a short line as-is and respect
    MAX_LINE_LENGTH.
    """
    mock_view = mock.MagicMock()
    # a simple to format list running 94 characters long plus newline
    long_list = "[{}{}]\n".format(*("(1, 2), " * 10, '"0123456789"'))
    tab = mock_view.current_tab
    tab.text.return_value = long_list
    with mock.patch("mu.logic.MAX_LINE_LENGTH", 94):
        ed = mu.logic.Editor(mock_view)
        too_long = mu.logic.check_pycodestyle(tab.text.return_value)
        assert len(too_long) == 0  # No issues
        ed.tidy_code()
        called_with = tab.SendScintilla.call_args[0][1].decode()
        tab.text.return_value = called_with
        ok = mu.logic.check_pycodestyle(tab.text.return_value)
        assert len(ok) == 0  # No issues

    assert tab.text.return_value == long_list


def test_device_init(microbit_com1):
    """
    Test that all properties are set properly and can be read.
    """
    assert microbit_com1.vid == 0x0D28
    assert microbit_com1.pid == 0x0204
    assert microbit_com1.port == "COM1"
    assert microbit_com1.serial_number == 123456
    assert microbit_com1.long_mode_name == "BBC micro:bit"
    assert microbit_com1.short_mode_name == "microbit"


def test_device_with_no_board_name_is_mode_name(esp_device):
    """
    Test that when no board name is given, the board name is the same
    as the mode name.
    """
    assert esp_device.name == "ESP MicroPython compatible"


def test_com1_equality(microbit_com1):
    """
    Test that two separate Device-objects representing the same device
    are recognized as equal.
    """
    identical_microbit_com1 = mu.logic.Device(
        0x0D28,
        0x0204,
        "COM1",
        123456,
        "ARM",
        "BBC micro:bit",
        "microbit",
        "BBC micro:bit",
    )
    assert microbit_com1 == identical_microbit_com1


def test_com1_not_equal_on_different_ports(microbit_com1):
    """
    Test that if two otherwise identical devices differ on the port, they
    are not recognized as being equal.
    """
    microbit_com2 = mu.logic.Device(
        0x0D28,
        0x0204,
        "COM2",
        123456,
        "ARM",
        "BBC micro:bit",
        "microbit",
        "BBC micro:bit",
    )
    assert microbit_com1 != microbit_com2


def test_com1_hash_equality(microbit_com1):
    """
    Test that hash function returns the same for two identical Device-objects.
    """
    identical_microbit_com1 = mu.logic.Device(
        0x0D28,
        0x0204,
        "COM1",
        123456,
        "ARM",
        "BBC micro:bit",
        "microbit",
        "BBC micro:bit",
    )
    assert hash(microbit_com1) == hash(identical_microbit_com1)


def test_com1_hash_not_equal_on_different_ports(microbit_com1):
    """
    Test that the hash function differs, when two otherwise identical
    devices are connected to two different ports.
    """
    microbit_com2 = mu.logic.Device(
        0x0D28,
        0x0204,
        "COM2",
        123456,
        "ARM",
        "BBC micro:bit",
        "microbit",
        "BBC micro:bit",
    )
    assert hash(microbit_com1) != hash(microbit_com2)
