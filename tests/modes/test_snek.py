# -*- coding: utf-8 -*-
"""
Tests for the Snek mode.
"""

from unittest import mock

import pytest
from PyQt6.QtWidgets import QMessageBox

from mu.logic import Device
from mu.modes.api import SNEK_APIS
from mu.modes.snek import REPLConnection, SnekMode, SnekREPLConnection


@pytest.fixture()
def snek_device():
    return Device(
        0x0403, 0x6001, "COM0", "123456", "Snek", "Snekboard", "snek"
    )


def test_snek_repl_connection_init_defaults():
    """
    Test SnekREPLConnection __init__ with default arguments.
    """
    port = "COM1"
    conn = SnekREPLConnection(port)
    assert conn.flowcontrol is False
    assert conn.sent == 0
    assert conn.chunk == 16
    assert conn.data == b""
    assert conn.waiting is False
    assert conn.ready is False
    assert conn.pending == b""
    assert conn.wait_for_data is False
    assert conn.got_dc4 is False
    assert conn._baudrate == 115200
    assert conn.port == port


def test_snek_repl_connection_init_custom_args():
    """
    Test SnekREPLConnection __init__ with custom arguments.
    """
    port = "COM2"
    conn = SnekREPLConnection(
        port,
        baudrate=57600,
        flowcontrol=True,
        chunk=32,
        wait_for_data=True,
    )
    assert conn.flowcontrol is True
    assert conn.sent == 0
    assert conn.chunk == 32
    assert conn.data == b""
    assert conn.waiting is False
    assert conn.ready is False
    assert conn.pending == b""
    assert conn.wait_for_data is True
    assert conn.got_dc4 is False
    assert conn._baudrate == 57600
    assert conn.port == port


def test_set_ready_already_ready():
    """
    If already ready, set_ready should do nothing.
    """
    conn = SnekREPLConnection("COM1")
    conn.ready = True
    conn.pending = b"abc"
    conn.write = mock.MagicMock()
    conn.set_ready()
    conn.write.assert_not_called()
    assert conn.pending == b"abc"


def test_set_ready_no_flowcontrol():
    """
    If flowcontrol is False, should just call write with pending and clear pending.
    """
    conn = SnekREPLConnection("COM1")
    conn.flowcontrol = False
    conn.ready = False
    conn.pending = b"xyz"
    conn.write = mock.MagicMock()
    conn.set_ready()
    conn.write.assert_called_once_with(b"xyz")
    assert conn.pending == b""


def test_set_ready_with_flowcontrol_autobaud_response_detected():
    """
    If flowcontrol is True and got_dc4 is set after first baudrate, should break early.
    """
    conn = SnekREPLConnection("COM1")
    conn.flowcontrol = True
    conn.ready = False
    conn.pending = b"123"
    conn.serial = mock.MagicMock()
    conn.got_dc4 = False

    def waitForReadyRead(timeout):
        conn.got_dc4 = True

    conn.serial.waitForReadyRead.side_effect = waitForReadyRead
    conn.write = mock.MagicMock()
    conn.set_ready()
    assert conn.serial.setBaudRate.call_count >= 1
    assert conn.serial.write.call_count >= 1
    assert conn.serial.waitForReadyRead.call_count >= 1
    conn.write.assert_called_once_with(b"123")
    assert conn.pending == b""


def test_set_ready_with_flowcontrol_no_autobaud_response():
    """
    If flowcontrol is True and got_dc4 is never set, should use default baudrate.
    """
    conn = SnekREPLConnection("COM1")
    conn.flowcontrol = True
    conn.ready = False
    conn.pending = b"456"
    conn.serial = mock.MagicMock()
    conn.got_dc4 = False

    def waitForReadyRead(timeout):
        pass

    conn.serial.waitForReadyRead.side_effect = waitForReadyRead
    conn.write = mock.MagicMock()
    conn.set_ready()
    assert conn.serial.setBaudRate.call_count >= 1
    assert conn.serial.write.call_count >= 1
    assert conn.serial.waitForReadyRead.call_count >= 1
    conn.write.assert_called_once_with(b"456")
    assert conn.pending == b""


def test_open_calls_super_and_set_ready_no_wait_for_data():
    """
    If wait_for_data is False, open should call super().open() and set_ready().
    """
    conn = SnekREPLConnection("COM1")
    conn.wait_for_data = False
    conn.set_ready = mock.MagicMock()
    with mock.patch.object(SnekREPLConnection, "open", wraps=conn.open):
        with mock.patch.object(REPLConnection, "open") as super_open:
            conn.open()
            super_open.assert_called_once_with()
            conn.set_ready.assert_called_once_with()


def test_open_wait_for_data_sets_timer():
    """
    If wait_for_data is True, open should call QTimer.singleShot with 3000ms and set_ready.
    """
    conn = SnekREPLConnection("COM1")
    conn.wait_for_data = True
    conn.set_ready = mock.MagicMock()
    with (
        mock.patch.object(REPLConnection, "open") as super_open,
        mock.patch("mu.modes.snek.QTimer") as mock_qtimer,
    ):
        conn.open()
        super_open.assert_called_once_with()
        mock_qtimer.singleShot.assert_called_once()
        args, kwargs = mock_qtimer.singleShot.call_args
        assert args[0] == 3000
        ready_func = args[1]
        ready_func()
        conn.set_ready.assert_called_once_with()


def test_send_enq_sets_waiting_and_writes_enq():
    """
    Test that send_enq calls super().write with ENQ and sets waiting to True.
    """
    conn = SnekREPLConnection("COM1")
    conn.write = mock.MagicMock()
    with mock.patch.object(REPLConnection, "write") as super_write:
        conn.send_enq()
        super_write.assert_called_once_with(b"\x05")
        assert conn.waiting is True


def test_recv_ack_resets_sent_and_waiting_and_calls_send_data():
    """
    Test that recv_ack resets sent to 0, waiting to False, and calls send_data.
    """
    conn = SnekREPLConnection("COM1")
    conn.sent = 10
    conn.waiting = True
    conn.send_data = mock.MagicMock()
    conn.recv_ack()
    assert conn.sent == 0
    assert conn.waiting is False
    conn.send_data.assert_called_once_with()


def test_on_serial_read_ack_calls_recv_ack_and_removes_ack():
    """
    If ACK (\x06) is in data, recv_ack should be called and ACK removed from data.
    """
    conn = SnekREPLConnection("COM1")
    conn.serial = mock.MagicMock()
    conn.serial.readAll.return_value = b"abc\x06def"
    conn.recv_ack = mock.MagicMock()
    conn.got_dc4 = False
    conn.ready = True
    conn.data_received = mock.MagicMock()
    conn.data_received.emit = mock.MagicMock()
    conn._on_serial_read()
    conn.recv_ack.assert_called_once_with()
    emitted_data = conn.data_received.emit.call_args[0][0]
    assert b"\x06" not in emitted_data
    assert emitted_data == b"abcdef"


def test_on_serial_read_dc4_sets_got_dc4_and_removes_dc4():
    """
    If DC4 (\x14) is in data, got_dc4 should be set and DC4 removed from data.
    """
    conn = SnekREPLConnection("COM1")
    conn.serial = mock.MagicMock()
    conn.serial.readAll.return_value = b"foo\x14bar"
    conn.recv_ack = mock.MagicMock()
    conn.got_dc4 = False
    conn.ready = True
    conn.data_received = mock.MagicMock()
    conn.data_received.emit = mock.MagicMock()
    conn._on_serial_read()
    assert conn.got_dc4 is True
    emitted_data = conn.data_received.emit.call_args[0][0]
    assert b"\x14" not in emitted_data
    assert emitted_data == b"foobar"


def test_on_serial_read_ready_false_and_W_in_data_sets_ready_with_timer():
    """
    If not ready and 'W' in data, should set QTimer.singleShot(200, ready_func).
    """
    conn = SnekREPLConnection("COM1")
    conn.serial = mock.MagicMock()
    conn.serial.readAll.return_value = b"abcWdef"
    conn.recv_ack = mock.MagicMock()
    conn.got_dc4 = False
    conn.ready = False
    conn.data_received = mock.MagicMock()
    conn.data_received.emit = mock.MagicMock()
    conn.set_ready = mock.MagicMock()
    with mock.patch("mu.modes.snek.QTimer") as mock_qtimer:
        conn._on_serial_read()
        mock_qtimer.singleShot.assert_called_once()
        args, kwargs = mock_qtimer.singleShot.call_args
        assert args[0] == 200
        ready_func = args[1]
        ready_func()
        conn.set_ready.assert_called_once_with()


def test_on_serial_read_emits_data_received():
    """
    Should always emit data_received with processed data.
    """
    conn = SnekREPLConnection("COM1")
    conn.serial = mock.MagicMock()
    conn.serial.readAll.return_value = b"hello"
    conn.recv_ack = mock.MagicMock()
    conn.got_dc4 = False
    conn.ready = True
    conn.data_received = mock.MagicMock()
    conn.data_received.emit = mock.MagicMock()
    conn._on_serial_read()
    conn.data_received.emit.assert_called_once_with(b"hello")


def test_send_data_no_data():
    """
    If self.data is empty, send_data should do nothing.
    """
    conn = SnekREPLConnection("COM1")
    conn.waiting = False
    conn.data = b""
    with mock.patch.object(REPLConnection, "write") as super_write:
        conn.send_data()
        super_write.assert_not_called()


def test_send_data_waiting_true():
    """
    If self.waiting is True, send_data should do nothing.
    """
    conn = SnekREPLConnection("COM1")
    conn.waiting = True
    conn.data = b"abc"
    with mock.patch.object(REPLConnection, "write") as super_write:
        conn.send_data()
        super_write.assert_not_called()


def test_send_data_less_than_chunk():
    """
    If data length is less than chunk, should write all data and not call send_enq.
    """
    conn = SnekREPLConnection("COM1")
    conn.waiting = False
    conn.chunk = 10
    conn.sent = 0
    conn.data = b"abc"
    with (
        mock.patch.object(REPLConnection, "write") as super_write,
        mock.patch.object(conn, "send_enq") as send_enq,
    ):
        conn.send_data()
        super_write.assert_called_once_with(b"abc")
        send_enq.assert_not_called()
        assert conn.sent == 3
        assert conn.data == b""


def test_send_data_exact_chunk():
    """
    If data length equals chunk, should write all data and call send_enq.
    """
    conn = SnekREPLConnection("COM1")
    conn.waiting = False
    conn.chunk = 3
    conn.sent = 0
    conn.data = b"xyz"
    with (
        mock.patch.object(REPLConnection, "write") as super_write,
        mock.patch.object(conn, "send_enq") as send_enq,
    ):
        conn.send_data()
        super_write.assert_called_once_with(b"xyz")
        send_enq.assert_called_once_with()
        assert conn.sent == 3
        assert conn.data == b""


def test_send_data_multiple_chunks():
    """
    If data is longer than chunk, should write chunk-sized pieces and call send_enq after each chunk.
    """
    conn = SnekREPLConnection("COM1")
    conn.waiting = False
    conn.chunk = 2
    conn.sent = 0
    conn.data = b"abcd"
    with (
        mock.patch.object(REPLConnection, "write") as super_write,
        mock.patch.object(conn, "send_enq") as send_enq,
    ):

        def set_waiting_true():
            conn.waiting = True

        send_enq.side_effect = set_waiting_true
        conn.send_data()
        super_write.assert_called_once_with(b"ab")
        send_enq.assert_called_once_with()
        assert conn.sent == 2
        assert conn.data == b"cd"


def test_write_not_ready_adds_to_pending():
    """
    If not ready, write should add data to pending and return.
    """
    conn = SnekREPLConnection("COM1")
    conn.ready = False
    conn.pending = b""
    conn.write(b"abc")
    assert conn.pending == b"abc"


def test_write_flowcontrol_with_ctrl_c_sets_data_and_resets_sent_and_waiting():
    """
    If flowcontrol is True and data contains Ctrl-C, should set data, reset sent/waiting, and call send_data.
    """
    conn = SnekREPLConnection("COM1")
    conn.ready = True
    conn.flowcontrol = True
    conn.data = b"old"
    conn.sent = 5
    conn.waiting = True
    conn.send_data = mock.MagicMock()
    conn.write(b"foo\x03bar")
    assert conn.data == b"foo\x03bar"
    assert conn.sent == 0
    assert conn.waiting is False
    conn.send_data.assert_called_once_with()


def test_write_flowcontrol_without_ctrl_c_appends_data_and_calls_send_data():
    """
    If flowcontrol is True and data does not contain Ctrl-C, should append to data and call send_data.
    """
    conn = SnekREPLConnection("COM1")
    conn.ready = True
    conn.flowcontrol = True
    conn.data = b"old"
    conn.send_data = mock.MagicMock()
    conn.write(b"abc")
    assert conn.data == b"oldabc"
    conn.send_data.assert_called_once_with()


def test_write_no_flowcontrol_calls_super_write():
    """
    If flowcontrol is False, should call super().write(data).
    """
    conn = SnekREPLConnection("COM1")
    conn.ready = True
    conn.flowcontrol = False
    with mock.patch.object(REPLConnection, "write") as super_write:
        conn.write(b"xyz")
        super_write.assert_called_once_with(b"xyz")


def test_send_interrupt_calls_write_with_ctrl_o_ctrl_c():
    """
    Test that send_interrupt calls write with Control-O and Control-C bytes.
    """
    conn = SnekREPLConnection("COM1")
    conn.write = mock.MagicMock()
    conn.send_interrupt()
    conn.write.assert_called_once_with(b"\x0f\x03")


def test_snek_mode():
    """
    Sanity check for setting up the mode.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    am = SnekMode(editor, view)
    assert am.name == "Snek"
    assert am.description == "Write code for boards running Snek."
    assert am.icon == "snek"
    assert am.editor == editor
    assert am.view == view

    actions = am.actions()
    assert 3 <= len(actions) <= 4
    assert actions[0]["name"] == "serial"
    assert actions[0]["handler"] == am.toggle_repl
    assert actions[1]["name"] == "flash"
    assert actions[1]["handler"] == am.put
    assert actions[2]["name"] == "getflash"
    assert actions[2]["handler"] == am.get

    # Sometimes charts just aren't available for testing
    if len(actions) == 4:
        assert actions[3]["name"] == "plotter"
        assert actions[3]["handler"] == am.toggle_plotter
    assert "code" not in am.module_names


def test_snek_put():
    """
    Put current editor contents to eeprom
    """

    class TestSnekMode(SnekMode):
        def toggle_repl(self, event):
            self.repl = True

    editor = mock.MagicMock()
    view = mock.MagicMock()
    mock_tab = mock.MagicMock()
    mock_tab.text.return_value = "# Write your code here :-)"
    view.current_tab = mock_tab
    view.repl_pane = mock.MagicMock()
    view.repl_pane.send_commands = mock.MagicMock()
    mm = TestSnekMode(editor, view)
    mm.repl = None
    mm.put()
    assert view.repl_pane.send_commands.call_count == 1
    assert (
        view.repl_pane.send_commands.call_args[0][0][0]
        == "eeprom.write()\n"
        + mock_tab.text.return_value
        + "\n"
        + "\x04reset()\n"
    )


def test_snek_put_empty():
    """
    Put empty editor contents to eeprom
    """

    class TestSnekMode(SnekMode):
        def toggle_repl(self, event):
            self.repl = True

    editor = mock.MagicMock()
    view = mock.MagicMock()
    mock_tab = mock.MagicMock()
    mock_tab.text.return_value = ""
    view.current_tab = mock_tab
    view.repl_pane = mock.MagicMock()
    view.repl_pane.send_commands = mock.MagicMock()
    print("send commands mock is %r" % view.repl_pane.send_commands)
    mm = TestSnekMode(editor, view)
    mm.repl = None
    mm.put()
    assert view.repl_pane.send_commands.call_count == 1
    assert (
        view.repl_pane.send_commands.call_args[0][0][0]
        == "eeprom.write()\n"
        + mock_tab.text.return_value
        + "\n"
        + "\x04reset()\n"
    )


def test_snek_put_none():
    """
    Put current editor contents to eeprom
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    view.current_tab = None
    view.repl_pane = mock.MagicMock()
    view.repl_pane.send_commands = mock.MagicMock()
    view.show_message = mock.MagicMock()
    mm = SnekMode(editor, view)
    mm.put()
    assert view.repl_pane.send_commands.call_count == 0


mm = None


def set_snek_repl(*args, **kwargs):
    mm.repl = True


def test_snek_get_new():
    """
    Get current editor contents to eeprom
    """
    global mm
    editor = mock.MagicMock()
    view = mock.MagicMock()
    view.repl_pane = mock.MagicMock()
    view.repl_pane.send_commands = mock.MagicMock()
    view.widgets = ()
    view.add_tab = mock.MagicMock()
    mm = SnekMode(editor, view)
    mm.repl = False
    mm.toggle_repl = mock.MagicMock()
    mm.toggle_repl.side_effect = set_snek_repl
    mm.get()
    assert mm.toggle_repl.call_count == 1
    assert view.repl_pane.send_commands.call_count == 1
    mm.recv_text("hello")
    assert view.add_tab.call_count == 1


def test_snek_get_existing():
    """
    Get current editor contents to eeprom
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    tab = mock.MagicMock()
    tab.path = None
    tab.setText = mock.MagicMock()
    tab.setModified(False)
    view.repl_pane = mock.MagicMock()
    view.repl_pane.send_commands = mock.MagicMock()
    view.widgets = (tab,)
    mm = SnekMode(editor, view)
    mm.repl = True
    mm.get()
    assert view.repl_pane.send_commands.call_count == 1
    mm.recv_text("hello")
    assert tab.setText.call_count == 1


def test_snek_get_existing_modified():
    """
    Get current editor contents into a modified buffer from eeprom
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    tab = mock.MagicMock()
    tab.path = None
    tab.setText = mock.MagicMock()
    tab.isModified.return_value = True

    mock_window = mock.MagicMock()
    mock_window.show_confirmation = mock.MagicMock(
        return_value=QMessageBox.Cancel
    )
    tab.nativeParentWidget = mock.MagicMock(return_value=mock_window)
    view.repl_pane = mock.MagicMock()
    view.repl_pane.send_commands = mock.MagicMock()
    view.widgets = (tab,)
    mm = SnekMode(editor, view)
    mm.repl = True
    mm.get()
    assert mock_window.show_confirmation.call_count == 1
    assert view.repl_pane.send_commands.call_count == 0


def test_api():
    """
    Ensure the correct API definitions are returned.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    am = SnekMode(editor, view)
    assert am.api() == SNEK_APIS


def test_snek_mode_add_repl_no_port():
    """
    If it's not possible to find a connected snek device then ensure a helpful
    message is enacted.
    """
    editor = mock.MagicMock()
    editor.current_device = None
    view = mock.MagicMock()
    view.show_message = mock.MagicMock()
    mm = SnekMode(editor, view)
    mm.add_repl()
    assert view.show_message.call_count == 1
    message = "Could not find an attached device."
    assert view.show_message.call_args[0][0] == message


def test_snek_mode_add_repl_ioerror(snek_device):
    """
    Sometimes when attempting to connect to the device there is an IOError
    because it's still booting up or connecting to the host computer. In this
    case, ensure a useful message is displayed.
    """
    editor = mock.MagicMock()
    editor.current_device = snek_device
    view = mock.MagicMock()
    view.show_message = mock.MagicMock()
    ex = IOError("Cannot connect to device on port COM0")
    mm = SnekMode(editor, view)
    mock_repl_connection = mock.MagicMock()
    mock_repl_connection.open = mock.MagicMock(side_effect=ex)
    mock_connection_class = mock.MagicMock(return_value=mock_repl_connection)
    with mock.patch("mu.modes.snek.SnekREPLConnection", mock_connection_class):
        mm.add_repl()
    assert view.show_message.call_count == 1
    assert view.show_message.call_args[0][0] == str(ex)


def test_snek_mode_add_repl_exception(snek_device):
    """
    Ensure that any non-IOError based exceptions are logged.
    """
    editor = mock.MagicMock()
    editor.current_device = snek_device
    view = mock.MagicMock()
    ex = Exception("BOOM")
    mm = SnekMode(editor, view)
    mock_repl_connection = mock.MagicMock()
    mock_repl_connection.open = mock.MagicMock(side_effect=ex)
    mock_connection_class = mock.MagicMock(return_value=mock_repl_connection)
    with mock.patch("mu.modes.snek.logger", return_value=None) as logger:
        with mock.patch(
            "mu.modes.snek.SnekREPLConnection", mock_connection_class
        ):
            mm.add_repl()
            logger.error.assert_called_once_with(ex)


def test_snek_mode_add_repl(snek_device):
    """
    Nothing goes wrong so check the _view.add_snek_repl gets the
    expected argument.
    """
    editor = mock.MagicMock()
    editor.current_device = snek_device
    view = mock.MagicMock()
    view.show_message = mock.MagicMock()
    view.add_snek_repl = mock.MagicMock()
    mm = SnekMode(editor, view)
    mock_repl_connection = mock.MagicMock()
    mock_connection_class = mock.MagicMock(return_value=mock_repl_connection)
    with mock.patch("mu.modes.snek.SnekREPLConnection", mock_connection_class):
        mm.add_repl()
    assert view.show_message.call_count == 0
    assert view.add_snek_repl.call_args[0][1] == mock_repl_connection
    mock_repl_connection.send_interrupt.assert_called_once_with()


def test_snek_mode_add_repl_no_force_interrupt(snek_device):
    """
    Nothing goes wrong so check the _view.add_snek_repl gets the
    expected arguments (including the flag so no keyboard interrupt is called).
    """
    editor = mock.MagicMock()
    editor.current_device = snek_device
    view = mock.MagicMock()
    view.show_message = mock.MagicMock()
    view.add_snek_repl = mock.MagicMock()
    mm = SnekMode(editor, view)
    mm.force_interrupt = False
    mock_repl_connection = mock.MagicMock()
    mock_connection_class = mock.MagicMock(return_value=mock_repl_connection)
    with mock.patch("mu.modes.snek.SnekREPLConnection", mock_connection_class):
        mm.add_repl()
    assert view.show_message.call_count == 0
    assert view.add_snek_repl.call_args[0][1] == mock_repl_connection
    assert mock_repl_connection.send_interrupt.call_count == 0


def test_snek_stop(snek_device):
    """
    Ensure that this method, called when Mu is quitting, shuts down
    the serial port.
    """
    editor = mock.MagicMock()
    editor.current_device = snek_device
    view = mock.MagicMock()
    mm = SnekMode(editor, view)
    view.remove_repl = mock.MagicMock()
    mm.stop()
    view.remove_repl.assert_called_once_with()


def test_device_changed(snek_device):
    """
    Ensure REPL pane is updated, when the user changes
    device.
    """
    view = mock.MagicMock()
    editor = mock.MagicMock()
    mm = SnekMode(editor, view)
    mm.repl = mock.MagicMock()
    mm.add_repl = mock.MagicMock()
    mm.remove_repl = mock.MagicMock()
    mm.plotter = mock.MagicMock()
    mm.add_plotter = mock.MagicMock()
    mm.remove_plotter = mock.MagicMock()
    mm.connection = mock.MagicMock()
    mm.device_changed(snek_device)
    mm.remove_repl.assert_called_once_with()
    mm.add_repl.assert_called_once_with()
    mm.remove_plotter.assert_called_once_with()
    mm.add_plotter.assert_called_once_with()
    mm.connection.send_interrupt.assert_called_once_with()
