"""
Tests for the minimalist Pico mode.
"""

from unittest import mock

import pytest

from mu.modes.api import SHARED_APIS
from mu.modes.pico import PicoMode


@pytest.fixture
def pico_mode():
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pico_mode = PicoMode(editor, view)
    return pico_mode


def test_pico_mode_init():
    """
    Sanity check for setting up the mode.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    pm = PicoMode(editor, view)
    assert pm.name == "RP2040"
    assert (
        pm.description == "Write MicroPython directly on a Raspberry Pi Pico."
    )
    assert pm.icon == "pico"
    assert pm.editor == editor
    assert pm.view == view


def test_api(pico_mode):
    """
    Ensure the right thing comes back from the API.
    """
    api = pico_mode.api()
    assert api == SHARED_APIS
