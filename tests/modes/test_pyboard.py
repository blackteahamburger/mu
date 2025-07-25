# -*- coding: utf-8 -*-
"""
Tests for the Pyboard mode.
"""

import ctypes
from unittest import mock

import pytest

from mu.modes.api import PYBOARD_APIS, SHARED_APIS
from mu.modes.pyboard import PyboardMode


@pytest.fixture
def windll():
    """
    Mocking the windll is tricky. It's not present on Posix platforms so
    we can't use standard patching. But it *is* present on Windows platforms
    so we need to unpatch once finished.
    """
    ctypes_has_windll = hasattr(ctypes, "windll")
    if ctypes_has_windll:
        mock_windll = mock.patch("ctypes.windll")
        mock_windll.start()
    else:
        mock_windll = mock.MagicMock()
        ctypes.windll = mock_windll

    yield mock_windll

    if ctypes_has_windll:
        mock_windll.stop()
    else:
        delattr(ctypes, "windll")


def test_pyboard_mode():
    """
    Sanity check for setting up the mode.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pbm = PyboardMode(editor, view)
    assert pbm.name == "Pyboard MicroPython"
    assert pbm.description == "Use MicroPython on the Pyboard line of boards."
    assert pbm.icon == "pyboard"
    assert pbm.editor == editor
    assert pbm.view == view

    actions = pbm.actions()
    assert len(actions) == 2
    assert actions[0]["name"] == "serial"
    assert actions[0]["handler"] == pbm.toggle_repl
    assert actions[1]["name"] == "plotter"
    assert actions[1]["handler"] == pbm.toggle_plotter
    assert "code" not in pbm.module_names


def test_workspace_dir_posix_exists():
    """
    Simulate being on os.name == 'posix' and a call to "mount" returns a
    record indicating a connected device.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pbm = PyboardMode(editor, view)
    with open("tests/modes/mount_exists.txt", "rb") as fixture_file:
        fixture = fixture_file.read()
        with mock.patch("os.name", "posix"):
            with mock.patch(
                "mu.modes.pyboard.check_output", return_value=fixture
            ):
                assert pbm.workspace_dir() == "/media/PYBFLASH"


def test_workspace_dir_posix_no_mount_command():
    """
    When the user doesn't have administrative privileges on OSX then the mount
    command isn't on their path. In which case, check Mu uses the more
    explicit /sbin/mount instead.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pbm = PyboardMode(editor, view)
    with open("tests/modes/mount_exists.txt", "rb") as fixture_file:
        fixture = fixture_file.read()
    mock_check = mock.MagicMock(side_effect=[FileNotFoundError, fixture])
    with (
        mock.patch("os.name", "posix"),
        mock.patch("mu.modes.pyboard.check_output", mock_check),
    ):
        assert pbm.workspace_dir() == "/media/PYBFLASH"
        assert mock_check.call_count == 2
        assert mock_check.call_args_list[0][0][0] == "mount"
        assert mock_check.call_args_list[1][0][0] == "/sbin/mount"


def test_workspace_dir_posix_missing():
    """
    Simulate being on os.name == 'posix' and a call to "mount" returns a
    no records associated with a micro:bit device.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pbm = PyboardMode(editor, view)
    with open("tests/modes/mount_missing.txt", "rb") as fixture_file:
        fixture = fixture_file.read()
        with mock.patch("os.name", "posix"):
            with (
                mock.patch(
                    "mu.modes.pyboard.check_output", return_value=fixture
                ),
                mock.patch(
                    "mu.modes.pyboard.MicroPythonMode.workspace_dir"
                ) as mpm,
            ):
                mpm.return_value = "foo"
                assert pbm.workspace_dir() == "foo"


def test_workspace_dir_nt_exists(windll):
    """
    Simulate being on os.name == 'nt' and a disk with a volume name 'PYBFLASH'
    exists indicating a connected device.
    """
    # ~ mock_windll = mock.MagicMock()
    # ~ mock_windll.kernel32 = mock.MagicMock()
    # ~ mock_windll.kernel32.GetVolumeInformationW = mock.MagicMock()
    # ~ mock_windll.kernel32.GetVolumeInformationW.return_value = None
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pbm = PyboardMode(editor, view)
    with mock.patch("os.name", "nt"):
        with mock.patch("os.path.exists", return_value=True):
            return_value = ctypes.create_unicode_buffer("PYBFLASH")
            with mock.patch(
                "ctypes.create_unicode_buffer", return_value=return_value
            ):
                assert pbm.workspace_dir() == "A:\\"


def test_workspace_dir_nt_missing(windll):
    """
    Simulate being on os.name == 'nt' and a disk with a volume name 'PYBFLASH'
    does not exist for a device.
    """
    # ~ mock_windll = mock.MagicMock()
    # ~ mock_windll.kernel32 = mock.MagicMock()
    # ~ mock_windll.kernel32.GetVolumeInformationW = mock.MagicMock()
    # ~ mock_windll.kernel32.GetVolumeInformationW.return_value = None
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pbm = PyboardMode(editor, view)
    with mock.patch("os.name", "nt"):
        with mock.patch("os.path.exists", return_value=True):
            return_value = ctypes.create_unicode_buffer(1024)
            with (
                mock.patch(
                    "ctypes.create_unicode_buffer", return_value=return_value
                ),
                mock.patch(
                    "mu.modes.pyboard.MicroPythonMode.workspace_dir"
                ) as mpm,
            ):
                mpm.return_value = "foo"
                assert pbm.workspace_dir() == "foo"


def test_workspace_dir_unknown_os():
    """
    Raises a NotImplementedError if the host OS is not supported.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pbm = PyboardMode(editor, view)
    with mock.patch("os.name", "foo"):
        with pytest.raises(NotImplementedError) as ex:
            pbm.workspace_dir()
    assert ex.value.args[0] == 'OS "foo" not supported.'


def test_api():
    """
    Ensure the correct API definitions are returned.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pbm = PyboardMode(editor, view)
    assert pbm.api() == SHARED_APIS + PYBOARD_APIS
