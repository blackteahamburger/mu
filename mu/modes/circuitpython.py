"""
A mode for working with Circuit Python boards.

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

import ctypes
import logging
import os
from subprocess import check_output

from adafruit_board_toolkit import circuitpython_serial

from mu.logic import Device
from mu.modes.api import ADAFRUIT_APIS, SHARED_APIS
from mu.modes.base import MicroPythonMode

logger = logging.getLogger(__name__)


class CircuitPythonMode(MicroPythonMode):
    """
    Represents the functionality required by the CircuitPython mode.
    """

    short_name = "circuitpython"
    icon = "circuitpython"
    save_timeout = 0  #: No auto-save on CP boards. Will restart.
    connected = True  #: is the board connected.
    force_interrupt = False  #: NO keyboard interrupt on serial connection.

    # Modules built into CircuitPython which mustn't be used as file names
    # for source code.
    module_names = {
        "_bleio",
        "_eve",
        "_pew",
        "_pixelbuf",
        "_stage",
        "_typing",
        "adafruit_bus_device",
        "aesio",
        "alarm",
        "array",
        "analogio",
        "audiobusio",
        "audiocore",
        "audioio",
        "audiomixer",
        "audiomp3",
        "audiopwmio",
        "binascii",
        "bitbangio",
        "bitmaptools",
        "bitops",
        "board",
        "builtins",
        "busio",
        "camera",
        "canio",
        "collections",
        "countio",
        "digitalio",
        "displayio",
        "dualbank",
        "errno",
        "fontio",
        "framebufferio",
        "frequencyio",
        "gamepad",
        "gamepadshift",
        "gc",
        "gnss",
        "hashlib",
        "i2cperipheral",
        "io",
        "ipaddress",
        "json",
        "math",
        "memorymonitor",
        "microcontroller",
        "msgpack",
        "multiterminal",
        "neopixel_write",
        "network",
        "nvm",
        "os",
        "ps2io",
        "pulseio",
        "pwmio",
        "random",
        "re",
        "rgbmatrix",
        "rotaryio",
        "rtc",
        "sdcardio",
        "sdioio",
        "sharpdisplay",
        "socket",
        "socketpool",
        "ssl",
        "storage",
        "struct",
        "supervisor",
        "sys",
        "terminalio",
        "time",
        "touchio",
        "uheap",
        "usb_cdc",
        "usb_hid",
        "usb_midi",
        "ustack",
        "vectorio",
        "watchdog",
        "wifi",
        "wiznet",
        "zlib",
    }

    @property
    def name(self):
        """
        Get the name of the mode.
        """
        return _("CircuitPython")

    @property
    def description(self):
        """
        Get a description of the mode.
        """
        return _("Write code for boards running CircuitPython.")

    def actions(self):
        """
        Return an ordered list of actions provided by this module. An action
        is a name (also used to identify the icon) , description, and handler.
        """
        buttons = [
            {
                "name": "serial",
                "display_name": _("Serial"),
                "description": _("Open a serial connection to your device."),
                "handler": self.toggle_repl,
                "shortcut": "CTRL+Shift+U",
            }
        ]
        buttons.append({
            "name": "plotter",
            "display_name": _("Plotter"),
            "description": _("Plot incoming REPL data."),
            "handler": self.toggle_plotter,
            "shortcut": "CTRL+Shift+P",
        })
        return buttons

    def workspace_dir(self):
        """
        Return the default location on the filesystem for opening and closing
        files.
        """
        device_dir = None
        # Attempts to find the path on the filesystem that represents the
        # plugged in CIRCUITPY board.
        if os.name == "posix":
            # We're on Linux or OSX
            for mount_command in ["mount", "/sbin/mount"]:
                try:
                    mount_output = check_output(mount_command).splitlines()
                    mounted_volumes = [x.split()[2] for x in mount_output]
                    for volume in mounted_volumes:
                        tail = os.path.split(volume)[-1]
                        if tail.startswith(b"CIRCUITPY") or tail.startswith(
                            b"PYBFLASH"
                        ):
                            device_dir = volume.decode("utf-8")
                            break
                except FileNotFoundError:
                    pass
                except PermissionError as e:
                    logger.error(
                        "Received '{}' running command: {}".format(
                            repr(e), mount_command
                        )
                    )
                    m = _("Permission error running mount command")
                    info = _(
                        'The mount command ("{}") returned an error: '
                        "{}. Mu will continue as if a device isn't "
                        "plugged in."
                    ).format(mount_command, repr(e))
                    self.view.show_message(m, info)
                # Avoid crashing Mu, the workspace dir will be set to default
                except Exception as e:
                    logger.error(
                        "Received '{}' running command: {}".format(
                            repr(e), mount_command
                        )
                    )
            if os.path.exists("/mnt/chromeos"):
                # We're on ChromeOS
                if os.path.exists("/mnt/chromeos/removable/CIRCUITPY/"):
                    device_dir = "/mnt/chromeos/removable/CIRCUITPY/"
                else:
                    m = _(
                        "If your Circuit Python device is plugged in,"
                        + ' you need to "Share with Linux" on the CIRCUITPY drive'
                        + ' in the "Files" app then restart Mu.'
                    )
                    self.view.show_message(m)

        elif os.name == "nt":
            # We're on Windows.

            def get_volume_name(disk_name):
                """
                Each disk or external device connected to windows has an
                attribute called "volume name". This function returns the
                volume name for the given disk/device.

                Code from http://stackoverflow.com/a/12056414
                """
                vol_name_buf = ctypes.create_unicode_buffer(1024)
                ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(disk_name),
                    vol_name_buf,
                    ctypes.sizeof(vol_name_buf),
                    None,
                    None,
                    None,
                    None,
                    0,
                )
                return vol_name_buf.value

            #
            # In certain circumstances, volumes are allocated to USB
            # storage devices which cause a Windows popup to raise if their
            # volume contains no media. Wrapping the check in SetErrorMode
            # with SEM_FAILCRITICALERRORS (1) prevents this popup.
            #
            old_mode = ctypes.windll.kernel32.SetErrorMode(1)
            try:
                for disk in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                    path = "{}:\\".format(disk)
                    if (
                        os.path.exists(path)
                        and get_volume_name(path) == "CIRCUITPY"
                    ):
                        return path
            finally:
                ctypes.windll.kernel32.SetErrorMode(old_mode)
        else:
            # No support for unknown operating systems.
            raise NotImplementedError('OS "{}" not supported.'.format(os.name))

        if device_dir:
            # Found it!
            self.connected = True
            return device_dir
        else:
            # Not plugged in? Just return Mu's regular workspace directory
            # after warning the user.
            wd = super().workspace_dir()
            if self.connected:
                m = _("Could not find an attached CircuitPython device.")
                info = _(
                    "Python files for CircuitPython devices"
                    " are stored on the device. Therefore, to edit"
                    " these files you need to have the device plugged in."
                    " Until you plug in a device, Mu will use the"
                    " directory found here:\n\n"
                    " {}\n\n...to store your code."
                )
                self.view.show_message(m, info.format(wd))
                self.connected = False
            return wd

    def compatible_board(self, port):
        """
        Use adafruit_board_toolkit to find out whether a board is running
        CircuitPython. The toolkit sees if the CDC Interface name is appropriate.
        """
        pid = port.productIdentifier()
        vid = port.vendorIdentifier()
        manufacturer = port.manufacturer()
        serial_number = port.serialNumber()
        port_name = self.port_path(port.portName())

        # Find all the CircuitPython REPL comports,
        # and see if any of their device names match the one passed in.
        for comport in circuitpython_serial.repl_comports():
            if comport.device == port_name:
                return Device(
                    vid,
                    pid,
                    port_name,
                    serial_number,
                    manufacturer,
                    self.name,
                    self.short_name,
                    "CircuitPython board",
                )
        # No match.
        return None

    def api(self):
        """
        Return a list of API specifications to be used by auto-suggest and call
        tips.
        """
        return SHARED_APIS + ADAFRUIT_APIS
