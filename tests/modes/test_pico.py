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


def test_api(pico_mode):
    """
    Ensure the right thing comes back from the API.
    """
    api = pico_mode.api()
    assert api == SHARED_APIS
