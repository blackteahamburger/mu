"""
UI related code for dialogs used by Mu.

Copyright (c) 2015-2017 Nicholas H.Tollervey and others (see the AUTHORS file).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

import logging
import os
import sys

from PyQt6.QtCore import QProcess, QSize, Qt, QTimer
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from mu.interface.widgets import DeviceSelector
from mu.resources import load_icon

logger = logging.getLogger(__name__)


class ModeItem(QListWidgetItem):
    """
    Represents an available mode listed for selection.
    """

    def __init__(self, name, description, icon, parent=None):
        """
        Instantiate a mode item with the given name, description, and icon.
        """
        super().__init__(parent)
        self.name = name
        self.description = description
        self.icon = icon
        text = "{}\n{}".format(name, description)
        self.setText(text)
        self.setIcon(load_icon(self.icon))


class ModeSelector(QDialog):
    """
    Defines a UI for selecting the mode for Mu.
    """

    def __init__(self, parent=None):
        """
        Instantiate a mode selector dialog.
        """
        super().__init__(parent)

    def setup(self, modes, current_mode):
        """
        Set up the mode selector dialog with available modes.
        """
        self.setMinimumSize(600, 400)
        self.setWindowTitle(_("Select Mode"))
        widget_layout = QVBoxLayout()
        label = QLabel(
            _(
                'Please select the desired mode then click "OK". '
                'Otherwise, click "Cancel".'
            )
        )
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        self.setLayout(widget_layout)
        self.mode_list = QListWidget()
        self.mode_list.itemDoubleClicked.connect(self.select_and_accept)
        widget_layout.addWidget(self.mode_list)
        self.mode_list.setIconSize(QSize(48, 48))
        for name, item in modes.items():
            if not item.is_debugger:
                litem = ModeItem(
                    item.name, item.description, item.icon, self.mode_list
                )
                if item.icon == current_mode:
                    self.mode_list.setCurrentItem(litem)
        self.mode_list.sortItems()
        instructions = QLabel(
            _(
                "Change mode at any time by clicking "
                'the "Mode" button containing Mu\'s logo.'
            )
        )
        instructions.setWordWrap(True)
        widget_layout.addWidget(instructions)
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        widget_layout.addWidget(button_box)

    def select_and_accept(self):
        """
        Handler for when an item is double-clicked.
        """
        self.accept()

    def get_mode(self):
        """
        Return details of the newly selected mode.
        """
        if self.result() == QDialog.Accepted:
            return self.mode_list.currentItem().icon
        else:
            raise RuntimeError("Mode change cancelled.")


class LogWidget(QWidget):
    """
    Used to display Mu's logs.
    """

    def setup(self, log):
        """
        Set up the log widget with the given log content.
        """
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        label = QLabel(
            _(
                "When reporting a bug, copy and paste the content of "
                "the following log file."
            )
        )
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        self.log_text_area = QPlainTextEdit()
        self.log_text_area.setReadOnly(True)
        self.log_text_area.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.log_text_area.setPlainText(log)
        widget_layout.addWidget(self.log_text_area)


class EnvironmentVariablesWidget(QWidget):
    """
    Used for editing and displaying environment variables used with Python 3
    mode.
    """

    def setup(self, envars):
        """
        Set up the environment variables widget with the given environment variables.
        """
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        label = QLabel(
            _(
                "The environment variables shown below will be "
                "set each time you run a Python 3 script.\n\n"
                "Each separate environment variable should be on a "
                "new line and of the form:\nNAME=VALUE"
            )
        )
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        self.text_area = QPlainTextEdit()
        self.text_area.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.text_area.setPlainText(envars)
        widget_layout.addWidget(self.text_area)


class MicrobitSettingsWidget(QWidget):
    """
    Used for configuring how to interact with the micro:bit:

    * Override runtime version to use.
    """

    def setup(self, custom_runtime_path):
        """
        Set up the micro:bit settings widget with the given runtime path.
        """
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        label = QLabel(
            _(
                "Override the built-in MicroPython runtime with "
                "the following hex file (empty means use the "
                "default):"
            )
        )
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        self.runtime_path = QLineEdit()
        self.runtime_path.setText(custom_runtime_path)
        self.btnFolder = QPushButton(_("Browse"))
        self.btnFolder.clicked.connect(self.show_folder_dialog)
        hbox = QHBoxLayout()
        hbox.addWidget(self.runtime_path)
        hbox.addWidget(self.btnFolder)
        widget_layout.addLayout(hbox)
        widget_layout.addStretch()

    def show_folder_dialog(self):
        """
        Show a file dialog to select a MicroPython runtime hex file.
        """
        # open dialog and set to foldername
        filename, _type = QFileDialog.getOpenFileName(
            self,
            _("Select MicroPython runtime (.hex)"),
            os.path.expanduser("."),
            _("MicroPython firmware (*.hex)"),
        )
        if filename:
            filename = filename.replace("/", os.sep)
            self.runtime_path.setText(filename)


class PythonAnywhereWidget(QWidget):
    """
    For configuring the user's username and API token for interacting with
    the PythonAnywhere API to deploy a website from web mode.
    """

    #: Valid server hosting instances for PythonAnywhere.
    valid_instances = [
        "www",
        "eu",
    ]

    def setup(self, username, token, instance="www"):
        """
        Set up the PythonAnywhere widget with the given username, token, and instance.
        """
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        label = QLabel(
            _(
                "The folks at "
                "<a href='https://www.pythonanywhere.com/'>PythonAnywhere</a> "
                "make it easy for learners and educators to host simple web "
                "projects for free. You'll need to sign up for an account and "
                "provide the following details for Mu to deploy your web "
                "project."
            )
        )
        label.setWordWrap(True)
        label.setOpenExternalLinks(True)
        widget_layout.addWidget(label)
        username_label = QLabel(
            _("\nCopy your username on PythonAnywhere into here:")
        )
        widget_layout.addWidget(username_label)
        self.username_text = QLineEdit()
        self.username_text.setPlaceholderText(_("username"))
        if username:
            self.username_text.setText(username)
        widget_layout.addWidget(self.username_text)
        token_label = QLabel(
            _(
                "Copy your "
                "<a href='https://www.pythonanywhere.com/account/#api_token'>"
                "secret API token from PythonAnywhere</a> into here:"
            )
        )
        token_label.setOpenExternalLinks(True)
        widget_layout.addWidget(token_label)
        self.token_text = QLineEdit()
        self.token_text.setPlaceholderText(_("secret api token"))
        if token:
            self.token_text.setText(token)
        widget_layout.addWidget(self.token_text)
        instance_label = QLabel(
            _("Server location ('www' is a safe default):")
        )
        widget_layout.addWidget(instance_label)
        self.instance_combo = QComboBox()
        selected = 0
        for pos, item in enumerate(self.valid_instances):
            self.instance_combo.addItem(item)
            if instance == item:
                selected = pos
        self.instance_combo.setCurrentIndex(selected)
        widget_layout.addWidget(self.instance_combo)
        widget_layout.addStretch()


class LocaleWidget(QWidget):
    """
    Used for manually setting the locale (and thus the language) used by Mu.
    """

    LANGUAGES = {
        _("Automatically detect"): "",
        "English": "en",
        "Deutsch": "de_DE",
        "Español": "es",
        "Français": "fr",
        "日本語": "ja",
        "Nederlands": "nl",
        "Polski": "pl",
        "Português (Br)": "pt_BR",
        "Português (Pt)": "pt_PT",
        "русский язык": "ru_RU",
        "Slovenský": "sk_SK",
        "Svenska": "sv",
        "tiếng Việt": "vi",
        "中文（简体）": "zh_CN",
        "中文（繁體）": "zh_TW",
    }

    def setup(self, locale):
        """
        Set up the locale widget with the given locale.
        """
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        self.drop_down = QComboBox()
        for k, v in self.LANGUAGES.items():
            self.drop_down.addItem(k, v)
        index = self.drop_down.findData(locale)
        if index > -1:
            self.drop_down.setCurrentIndex(index)
        label = QLabel(
            _(
                "Please select the language for Mu's user interface from the "
                "choices listed below. <strong>Restart Mu for these changes "
                "to take effect.</strong>"
            )
        )
        label.setWordWrap(True)
        widget_layout.addWidget(label)
        widget_layout.addWidget(self.drop_down)
        widget_layout.addStretch()

    def get_locale(self):
        """
        Return the user-selected language code.
        """
        return self.LANGUAGES.get(self.drop_down.currentText(), "")


class ESPFirmwareFlasherWidget(QWidget):
    """
    Used for configuring how to interact with the ESP:

    * Override MicroPython.
    """

    def setup(self, mode, device_list):
        """
        Set up the firmware flasher widget with the given mode and device list.
        """
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)

        # Instructions
        grp_instructions = QGroupBox(
            _("How to flash MicroPython to your device")
        )
        grp_instructions_vbox = QVBoxLayout()
        grp_instructions.setLayout(grp_instructions_vbox)
        # Note: we have to specify the link color here, to something
        # that's suitable for both day/night/contrast themes, as the
        # link color is not configurable in the Qt Stylesheets
        instructions = _(
            "&nbsp;1. Determine the type of device (ESP8266 or ESP32)<br />"
            "&nbsp;2. Download firmware from the "
            '<a href="https://micropython.org/download" '
            'style="color:#039be5;">'
            "https://micropython.org/download</a><br/>"
            "&nbsp;3. Connect your device<br/>"
            "&nbsp;4. Load the .bin file below using the 'Browse' button<br/>"
            "&nbsp;5. Press 'Erase & write firmware'"
            # "<br /><br />Check the current MicroPython version using the "
            # "following commands:<br />"
            # ">>> import sys<br />"
            # ">>> sys.implementation"
        )
        label = QLabel(instructions)
        label.setTextFormat(Qt.RichText)
        label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        label.setOpenExternalLinks(True)
        label.setWordWrap(True)
        grp_instructions_vbox.addWidget(label)
        widget_layout.addWidget(grp_instructions)

        # Device type, firmware path, flash button
        device_selector_label = QLabel(_("Device:"))
        self.device_selector = DeviceSelector(show_label=True, icon_first=True)
        self.device_selector.set_device_list(device_list)
        device_type_label = QLabel(_("Choose device type:"))
        self.device_type = QComboBox(self)
        self.device_type.addItem("ESP8266")
        self.device_type.addItem("ESP32")
        firmware_label = QLabel(_("Firmware (.bin):"))
        self.txtFolder = QLineEdit()
        self.btnFolder = QPushButton(_("Browse"))
        self.btnExec = QPushButton(_("Erase && write firmware"))
        self.btnExec.setEnabled(False)
        form_set = QGridLayout()
        form_set.addWidget(device_selector_label, 0, 0)
        form_set.addWidget(self.device_selector, 0, 1, 1, 3)
        form_set.addWidget(device_type_label, 1, 0)
        form_set.addWidget(self.device_type, 1, 1)
        form_set.addWidget(firmware_label, 2, 0)
        form_set.addWidget(self.txtFolder, 2, 1)
        form_set.addWidget(self.btnFolder, 2, 2)
        form_set.addWidget(self.btnExec, 2, 3)
        widget_layout.addLayout(form_set)

        # Output area
        self.log_text_area = QPlainTextEdit()
        self.log_text_area.setReadOnly(True)
        form_set = QHBoxLayout()
        form_set.addWidget(self.log_text_area)
        widget_layout.addLayout(form_set)

        # Connect events
        self.txtFolder.textChanged.connect(self.firmware_path_changed)
        self.btnFolder.clicked.connect(self.show_folder_dialog)
        self.btnExec.clicked.connect(self.update_firmware)
        self.device_selector.device_changed.connect(self.toggle_exec_button)

        self.mode = mode

    def show_folder_dialog(self):
        """
        Show a file dialog to select a MicroPython firmware binary file.
        """
        # open dialog and set to foldername
        filename, _type = QFileDialog.getOpenFileName(
            self,
            _("Select MicroPython firmware (.bin)"),
            os.path.expanduser("."),
            _("Firmware (*.bin)"),
        )
        if filename:
            filename = filename.replace("/", os.sep)
            self.txtFolder.setText(filename)

    def update_firmware(self):
        """
        Update the firmware on the selected device using esptool.
        """
        baudrate = 115200

        if self.mode.repl:
            self.mode.toggle_repl(None)
        if self.mode.plotter:
            self.mode.toggle_plotter(None)
        if self.mode.fs is not None:
            self.mode.toggle_files(None)

        device = self.device_selector.selected_device()
        if device is None:
            return

        esptool = "-mesptool"
        erase_command = '"{}" "{}" --port {} erase_flash'.format(
            sys.executable, esptool, device.port
        )

        if self.device_type.currentText() == "ESP32":
            write_command = (
                '"{}" "{}" --chip esp32 --port {} --baud {} '
                'write_flash -z 0x1000 "{}"'
            ).format(
                sys.executable,
                esptool,
                device.port,
                baudrate,
                self.txtFolder.text(),
            )
        else:
            write_command = (
                '"{}" "{}" --chip esp8266 --port {} --baud {} '
                'write_flash --flash_size=detect 0 "{}"'
            ).format(
                sys.executable,
                esptool,
                device.port,
                baudrate,
                self.txtFolder.text(),
            )

        self.commands = [erase_command, write_command]
        self.run_esptool()

    def run_esptool(self):
        """
        Run the esptool commands to flash the firmware.
        """
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardError.connect(self.read_process)
        self.process.readyReadStandardOutput.connect(self.read_process)
        self.process.finished.connect(self.esptool_finished)
        self.process.errorOccurred.connect(self.esptool_error)

        command = self.commands.pop(0)
        self.log_text_area.appendPlainText(command + "\n")
        self.process.startCommand(command)

    def esptool_error(self, error_num):
        """
        Handle errors that occur during the execution of esptool commands.
        """
        self.log_text_area.appendPlainText(
            "Error occurred: Error {}\n".format(error_num)
        )
        self.process = None

    def esptool_finished(self, exitCode, exitStatus):
        """
        Called when the subprocess that executes 'esptool.py is finished.
        """
        # Exit if a command fails
        if exitCode != 0 or exitStatus == QProcess.CrashExit:
            self.log_text_area.appendPlainText("Error on flashing. Aborting.")
            return
        if self.commands:
            self.process = None
            self.run_esptool()

    def read_process(self):
        """
        Read data from the child process and append it to the text area. Try
        to keep reading until there's no more data from the process.
        """
        msg = ""
        data = self.process.readAll()
        if data:
            try:
                msg = data.data().decode("utf-8")
                self.append_data(msg)
            except UnicodeDecodeError:
                pass
            QTimer.singleShot(2, self.read_process)

    def append_data(self, msg):
        """
        Add data to the end of the text area.
        """
        cursor = self.log_text_area.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(msg)
        cursor.movePosition(QTextCursor.End)
        self.log_text_area.setTextCursor(cursor)

    def firmware_path_changed(self):
        """
        Enable or disable the execute button based on the firmware path and
        the selected device.
        """
        self.toggle_exec_button()

    def toggle_exec_button(self):
        """
        Enable or disable the execute button based on the firmware path and
        the selected device.
        """
        if (
            len(self.txtFolder.text()) > 0
            and self.device_selector.selected_device() is not None
        ):
            self.btnExec.setEnabled(True)
        else:
            self.btnExec.setEnabled(False)


class AdminDialog(QDialog):
    """
    Displays administrative related information and settings (logs, environment
    variables etc...).
    """

    def __init__(self, parent=None):
        """
        Instantiate the admin dialog.
        """
        super().__init__(parent)
        self.microbit_widget = None
        self.envar_widget = None
        self.python_anywhere_widget = None

    def setup(self, log, settings, mode, device_list):
        """
        Set up the admin dialog with the given log, settings, mode, and device list.
        """
        self.setMinimumSize(600, 400)
        self.setWindowTitle(_("Mu Administration"))
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        self.tabs = QTabWidget()
        widget_layout.addWidget(self.tabs)
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        widget_layout.addWidget(button_box)
        # Tabs
        self.log_widget = LogWidget(self)
        self.log_widget.setup(log)
        self.tabs.addTab(self.log_widget, _("Current Log"))
        if mode.short_name in ["python", "web", "pygamezero"]:
            self.envar_widget = EnvironmentVariablesWidget(self)
            self.envar_widget.setup(settings.get("envars", ""))
            self.tabs.addTab(self.envar_widget, _("Python3 Environment"))
        if mode.short_name == "microbit":
            self.microbit_widget = MicrobitSettingsWidget(self)
            self.microbit_widget.setup(
                settings.get("microbit_runtime", ""),
            )
            self.tabs.addTab(self.microbit_widget, _("BBC micro:bit Settings"))
        if mode.short_name == "esp":
            self.esp_widget = ESPFirmwareFlasherWidget(self)
            self.esp_widget.setup(mode, device_list)
            self.tabs.addTab(self.esp_widget, _("ESP Firmware flasher"))
        if mode.short_name == "web":
            self.python_anywhere_widget = PythonAnywhereWidget(self)
            self.python_anywhere_widget.setup(
                settings.get("pa_username", ""),
                settings.get("pa_token", ""),
                settings.get("pa_instance", "www"),
            )
            self.tabs.addTab(
                self.python_anywhere_widget, _("PythonAnywhere API")
            )
        # Configure local.
        self.locale_widget = LocaleWidget(self)
        self.locale_widget.setup(settings.get("locale"))
        self.tabs.addTab(
            self.locale_widget, load_icon("language"), _("Select Language")
        )
        self.log_widget.log_text_area.setFocus()

    def settings(self):
        """
        Return a dictionary representation of the raw settings information
        generated by this dialog. Such settings will need to be processed /
        checked in the "logic" layer of Mu.
        """
        settings = {}
        if self.envar_widget:
            settings["envars"] = self.envar_widget.text_area.toPlainText()
        if self.microbit_widget:
            settings["microbit_runtime"] = (
                self.microbit_widget.runtime_path.text()
            )
        if self.python_anywhere_widget:
            settings["pa_username"] = (
                self.python_anywhere_widget.username_text.text().strip()
            )
            settings["pa_token"] = (
                self.python_anywhere_widget.token_text.text().strip()
            )
            settings["pa_instance"] = (
                self.python_anywhere_widget.instance_combo.currentText().strip()
            )
        settings["locale"] = self.locale_widget.get_locale()
        return settings


class FindReplaceDialog(QDialog):
    """
    Display a dialog for getting:

    * A term to find,
    * An optional value to replace the search term,
    * A flag to indicate if the user wishes to replace all.
    """

    def __init__(self, parent=None):
        """
        Instantiate a find/replace dialog.
        """
        super().__init__(parent)

    def setup(self, find=None, replace=None, replace_flag=False):
        """
        Set up the find/replace dialog with the given parameters.
        """
        self.setMinimumSize(600, 200)
        self.setWindowTitle(_("Find / Replace"))
        widget_layout = QVBoxLayout()
        self.setLayout(widget_layout)
        # Find.
        find_label = QLabel(_("Find:"))
        self.find_term = QLineEdit()
        self.find_term.setText(find)
        self.find_term.selectAll()
        widget_layout.addWidget(find_label)
        widget_layout.addWidget(self.find_term)
        # Replace
        replace_label = QLabel(_("Replace (optional):"))
        self.replace_term = QLineEdit()
        self.replace_term.setText(replace)
        widget_layout.addWidget(replace_label)
        widget_layout.addWidget(self.replace_term)
        # Global replace.
        self.replace_all_flag = QCheckBox(_("Replace all?"))
        self.replace_all_flag.setChecked(replace_flag)
        widget_layout.addWidget(self.replace_all_flag)
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        widget_layout.addWidget(button_box)

    def find(self):
        """
        Return the value the user entered to find.
        """
        return self.find_term.text()

    def replace(self):
        """
        Return the value the user entered for replace.
        """
        return self.replace_term.text()

    def replace_flag(self):
        """
        Return the value of the global replace flag.
        """
        return self.replace_all_flag.isChecked()
