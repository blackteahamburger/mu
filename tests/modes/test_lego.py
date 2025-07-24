"""
Tests for the minimalist Lego Spike mode.
"""

from unittest import mock

import pytest

from mu.modes.api import LEGO_APIS, SHARED_APIS
from mu.modes.lego import LegoMode


@pytest.fixture
def lego_mode():
    editor = mock.MagicMock()
    view = mock.MagicMock()
    lego_mode = LegoMode(editor, view)
    return lego_mode


def test_lego_mode_init():
    """
    Sanity check for setting up the mode.
    """
    editor = mock.MagicMock()
    view = mock.MagicMock()
    lego_mode = LegoMode(editor, view)
    assert lego_mode.name == "Lego MicroPython"
    assert (
        lego_mode.description
        == "Write MicroPython directly on Lego Spike devices."
    )
    assert lego_mode.icon == "lego"


def test_api(lego_mode):
    """
    Ensure the right thing comes back from the API.
    """
    api = lego_mode.api()
    assert api == SHARED_APIS + LEGO_APIS
