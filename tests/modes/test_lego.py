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


def test_api(lego_mode):
    """
    Ensure the right thing comes back from the API.
    """
    api = lego_mode.api()
    assert api == SHARED_APIS + LEGO_APIS
