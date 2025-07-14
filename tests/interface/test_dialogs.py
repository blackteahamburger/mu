# -*- coding: utf-8 -*-
"""
Tests for the user interface elements of Mu.
"""

import os
from unittest import mock

import pytest
from PyQt6.QtCore import QProcess
from PyQt6.QtWidgets import QDialog, QWidget

import mu.interface.dialogs
import mu.logic
from mu.modes import (
    CircuitPythonMode,
    DebugMode,
    ESPMode,
    MicrobitMode,
    PythonMode,
)


def test_ModeItem_init():
    """
    Ensure that ModeItem objects are setup correctly.
    """
    name = "item_name"
    description = "item_description"
    icon = "icon_name"
    mock_text = mock.MagicMock()
    mock_icon = mock.MagicMock()
    mock_load = mock.MagicMock(return_value=icon)
    with (
        mock.patch("mu.interface.dialogs.QListWidgetItem.setText", mock_text),
        mock.patch("mu.interface.dialogs.QListWidgetItem.setIcon", mock_icon),
        mock.patch("mu.interface.dialogs.load_icon", mock_load),
    ):
        mi = mu.interface.dialogs.ModeItem(name, description, icon)
        assert mi.name == name
        assert mi.description == description
        assert mi.icon == icon
    mock_text.assert_called_once_with("{}\n{}".format(name, description))
    mock_load.assert_called_once_with(icon)
    mock_icon.assert_called_once_with(icon)


def test_ModeSelector_setup():
    """
    Ensure the ModeSelector dialog is setup properly given a list of modes.

    If a mode has debugger = True it is ignored since debug mode is not a mode
    to be selected by users.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    modes = {
        "python": PythonMode(editor, view),
        "circuitpython": CircuitPythonMode(editor, view),
        "microbit": MicrobitMode(editor, view),
        "debugger": DebugMode(editor, view),
    }
    current_mode = "python"
    mock_item = mock.MagicMock()
    with mock.patch("mu.interface.dialogs.ModeItem", mock_item):
        with mock.patch("mu.interface.dialogs.QVBoxLayout"):
            with mock.patch("mu.interface.dialogs.QListWidget"):
                ms = mu.interface.dialogs.ModeSelector()
                ms.setLayout = mock.MagicMock()
                ms.setup(modes, current_mode)
                assert ms.setLayout.call_count == 1
    assert mock_item.call_count == 3


def test_ModeSelector_select_and_accept():
    """
    Ensure the accept slot is fired when this event handler is called.
    """
    ms = mu.interface.dialogs.ModeSelector()
    ms.accept = mock.MagicMock()
    ms.select_and_accept()
    ms.accept.assert_called_once_with()


def test_ModeSelector_get_mode():
    """
    Ensure that the ModeSelector will correctly return a selected mode (or
    raise the expected exception if cancelled).
    """
    ms = mu.interface.dialogs.ModeSelector()
    ms.result = mock.MagicMock(return_value=QDialog.Accepted)
    item = mock.MagicMock()
    item.icon = "name"
    ms.mode_list = mock.MagicMock()
    ms.mode_list.currentItem.return_value = item
    result = ms.get_mode()
    assert result == "name"
    ms.result.return_value = None
    with pytest.raises(RuntimeError):
        ms.get_mode()


def test_LogWidget_setup():
    """
    Ensure the log widget displays the referenced log file string in the
    expected way.
    """
    log = "this is the contents of a log file"
    lw = mu.interface.dialogs.LogWidget()
    lw.setup(log)
    assert lw.log_text_area.toPlainText() == log
    assert lw.log_text_area.isReadOnly()


def test_EnvironmentVariablesWidget_setup():
    """
    Ensure the widget for editing user defined environment variables displays
    the referenced string in the expected way.
    """
    envars = "name=value"
    evw = mu.interface.dialogs.EnvironmentVariablesWidget()
    evw.setup(envars)
    assert evw.text_area.toPlainText() == envars
    assert not evw.text_area.isReadOnly()


def test_MicrobitSettingsWidget_setup():
    """
    Ensure the widget for editing settings related to the BBC microbit
    displays the referenced settings data in the expected way.
    """
    custom_runtime_path = "/foo/bar"
    mbsw = mu.interface.dialogs.MicrobitSettingsWidget()
    mbsw.setup(custom_runtime_path)
    assert mbsw.runtime_path.text() == "/foo/bar"


def test_PythonAnywhereWidget_setup():
    """
    Ensure the widget for editing PythonAnywhere settings displays the
    referenced data in the expected way.
    """
    instance = "eu"
    username = "test_user"
    token = "test_token"
    paw = mu.interface.dialogs.PythonAnywhereWidget()
    paw.setup(username, token, instance)
    assert paw.username_text.text() == username
    assert paw.token_text.text() == token
    assert paw.instance_combo.currentText() == instance


@pytest.fixture
def microbit():
    device = mu.logic.Device(
        0x0D28,
        0x0204,
        "COM1",
        123456,
        "ARM",
        "BBC micro:bit",
        "microbit",
        None,
    )
    return device


def test_ESPFirmwareFlasherWidget_setup(microbit):
    """
    Ensure the widget for editing settings related to the ESP Firmware Flasher
    displays the referenced settings data in the expected way.
    """
    mode = mock.MagicMock()
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    device_list.add_device(microbit)
    espff = mu.interface.dialogs.ESPFirmwareFlasherWidget()
    with mock.patch("os.path.exists", return_value=False):
        espff.setup(mode, device_list)

    with mock.patch("os.path.exists", return_value=True):
        espff.setup(mode, device_list)


def test_ESPFirmwareFlasherWidget_show_folder_dialog(microbit):
    """
    Ensure the widget for editing settings related to the ESP Firmware Flasher
    displays the referenced settings data in the expected way.
    """
    mock_fd = mock.MagicMock()
    path = "/foo/bar.py"
    mock_fd.getOpenFileName = mock.MagicMock(return_value=(path, True))
    mode = mock.MagicMock()
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    device_list.add_device(microbit)
    espff = mu.interface.dialogs.ESPFirmwareFlasherWidget()
    with mock.patch("os.path.exists", return_value=True):
        espff.setup(mode, device_list)
    with mock.patch("mu.interface.dialogs.QFileDialog", mock_fd):
        espff.show_folder_dialog()
    assert espff.txtFolder.text() == path.replace("/", os.sep)


def test_ESPFirmwareFlasherWidget_update_firmware(microbit):
    """
    Ensure the widget for editing settings related to the ESP Firmware Flasher
    displays the referenced settings data in the expected way.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    mm = ESPMode(editor, view)
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    device_list.add_device(microbit)
    espff = mu.interface.dialogs.ESPFirmwareFlasherWidget()
    with mock.patch("os.path.exists", return_value=True):
        espff.setup(mm, device_list)

    espff.mode.repl = True
    espff.mode.plotter = True
    espff.mode.fs = True
    espff.device_type.setCurrentIndex(0)
    espff.update_firmware()

    espff.device_type.setCurrentIndex(1)
    espff.update_firmware()


def test_ESPFirmwareFlasherWidget_update_firmware_no_device():
    """
    Ensure that we don't try to flash, when no device is connected.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    mm = ESPMode(editor, view)
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    espff = mu.interface.dialogs.ESPFirmwareFlasherWidget()
    with mock.patch("os.path.exists", return_value=True):
        espff.setup(mm, device_list)

    espff.run_esptool = mock.MagicMock()
    espff.device_type.setCurrentIndex(0)
    espff.update_firmware()

    espff.run_esptool.assert_not_called()


def test_ESPFirmwareFlasherWidget_esptool_error(microbit):
    """
    Ensure the widget for editing settings related to the ESP Firmware Flasher
    displays the referenced settings data in the expected way.
    """
    mode = mock.MagicMock()
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    device_list.add_device(microbit)
    espff = mu.interface.dialogs.ESPFirmwareFlasherWidget()
    with mock.patch("os.path.exists", return_value=True):
        espff.setup(mode, device_list)
    espff.esptool_error(0)


def test_ESPFirmwareFlasherWidget_esptool_finished(microbit):
    """
    Ensure the widget for editing settings related to the ESP Firmware Flasher
    displays the referenced settings data in the expected way.
    """
    mode = mock.MagicMock()
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    device_list.add_device(microbit)
    espff = mu.interface.dialogs.ESPFirmwareFlasherWidget()
    espff.setup(mode, device_list)
    espff.esptool_finished(1, 0)
    assert "Error on flashing. Aborting." in espff.log_text_area.toPlainText()

    espff.log_text_area.clear()

    espff.commands = ["foo", "bar"]
    espff.esptool_finished(0, QProcess.NormalExit)
    assert "foo" in espff.log_text_area.toPlainText()

    espff.log_text_area.clear()

    espff.esptool_finished(0, QProcess.NormalExit)
    assert "bar" in espff.log_text_area.toPlainText()


def test_ESPFirmwareFlasherWidget_read_process(microbit):
    """
    Ensure the widget for editing settings related to the ESP Firmware Flasher
    displays the referenced settings data in the expected way.
    """
    mode = mock.MagicMock()
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    device_list.add_device(microbit)
    espff = mu.interface.dialogs.ESPFirmwareFlasherWidget()
    with mock.patch("os.path.exists", return_value=True):
        espff.setup(mode, device_list)

    espff.process = mock.MagicMock()
    espff.process.readAll().data.return_value = b"halted"
    espff.read_process()

    data = "𠜎Hello, World!".encode("utf-8")  # Contains a multi-byte char.
    data = data[1:]  # Split the muti-byte character (cause UnicodeDecodeError)
    espff.process.readAll().data.return_value = data
    espff.read_process()


def test_ESPFirmwareFlasherWidget_firmware_path_changed(microbit):
    """
    Ensure the widget for editing settings related to the ESP Firmware
    Flasher displays the referenced settings data in the expected way.
    """
    mode = mock.MagicMock()
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    device_list.add_device(microbit)
    espff = mu.interface.dialogs.ESPFirmwareFlasherWidget()
    with mock.patch("os.path.exists", return_value=True):
        espff.setup(mode, device_list)
    espff.txtFolder.setText("foo")
    assert espff.btnExec.isEnabled()
    espff.txtFolder.setText("")
    assert not espff.btnExec.isEnabled()


def test_AdminDialog_setup_python_mode():
    """
    Ensure the admin dialog is setup properly given the content of a log
    file and envars when in Python mode.
    """
    log = "this is the contents of a log file"
    settings = {
        "envars": "name=value",
        "locale": "",
    }
    mock_window = QWidget()
    mode = mock.MagicMock()
    mode.short_name = "python"
    mode.name = "Python 3"
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    ad = mu.interface.dialogs.AdminDialog(mock_window)
    ad.setup(log, settings, mode, device_list)
    assert ad.log_widget.log_text_area.toPlainText() == log
    s = ad.settings()
    assert s == settings


def test_AdminDialog_setup_microbit_mode():
    """
    Ensure the admin dialog is setup properly given the content of a log
    file and envars when in micro:bit mode.
    """
    log = "this is the contents of a log file"
    settings = {
        "microbit_runtime": "/foo/bar",
        "locale": "",
    }
    mock_window = QWidget()
    mode = mock.MagicMock()
    mode.short_name = "microbit"
    mode.name = "BBC micro:bit"
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    ad = mu.interface.dialogs.AdminDialog(mock_window)
    ad.setup(log, settings, mode, device_list)
    assert ad.log_widget.log_text_area.toPlainText() == log
    s = ad.settings()
    assert s == settings


def test_AdminDialog_setup_web_mode():
    """
    Ensure the admin dialog is setup properly given the content of a log
    file and envars when in web mode.
    """
    log = "this is the contents of a log file"
    settings = {
        "envars": "name=value",
        "locale": "",
        "pa_username": "test_user",
        "pa_token": "test_token",
        "pa_instance": "www",
    }
    mock_window = QWidget()
    mode = mock.MagicMock()
    mode.short_name = "web"
    mode.name = "Web mode"
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    ad = mu.interface.dialogs.AdminDialog(mock_window)
    ad.setup(log, settings, mode, device_list)
    assert ad.log_widget.log_text_area.toPlainText() == log
    s = ad.settings()
    assert s == settings


def test_AdminDialog_setup():
    """
    Ensure the admin dialog is setup properly given the content of a log
    file and envars.
    """
    log = "this is the contents of a log file"
    settings = {
        "locale": "",
    }
    mock_window = QWidget()
    mode = mock.MagicMock()
    mode.short_name = "esp"
    mode.name = "ESP MicroPython"
    modes = mock.MagicMock()
    device_list = mu.logic.DeviceList(modes)
    ad = mu.interface.dialogs.AdminDialog(mock_window)
    ad.setup(log, settings, mode, device_list)
    assert ad.log_widget.log_text_area.toPlainText() == log
    s = ad.settings()
    assert s == settings


def test_FindReplaceDialog_setup():
    """
    Ensure the find/replace dialog is setup properly given only the theme
    as an argument.
    """
    frd = mu.interface.dialogs.FindReplaceDialog()
    frd.setup()
    assert frd.find() == ""
    assert frd.replace() == ""
    assert frd.replace_flag() is False


def test_FindReplaceDialog_setup_with_args():
    """
    Ensure the find/replace dialog is setup properly given only the theme
    as an argument.
    """
    find = "foo"
    replace = "bar"
    flag = True
    frd = mu.interface.dialogs.FindReplaceDialog()
    frd.setup(find, replace, flag)
    assert frd.find() == find
    assert frd.replace() == replace
    assert frd.replace_flag()
