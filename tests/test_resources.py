# -*- coding: utf-8 -*-
"""
Tests for the resources sub-module.
"""

from pathlib import Path
from unittest import mock

from PyQt6.QtGui import QIcon, QMovie, QPixmap

import mu.resources


def test_path():
    """
    Ensure the path function under test returns the expected result.
    """
    mock_resources = Path("bar")
    with mock.patch(
        "mu.resources.importlib_files", return_value=mock_resources
    ):
        assert mu.resources.path("foo") == "bar/images/foo"


def test_load_icon():
    """
    Check the load_icon function returns the expected QIcon object.
    """
    result = mu.resources.load_icon("icon")
    assert isinstance(result, QIcon)


def test_load_pixmap():
    """
    Check the load_pixmap function returns the expected QPixmap object.
    """
    result = mu.resources.load_pixmap("icon")
    assert isinstance(result, QPixmap)


def test_load_movie():
    """
    Check the load_movie function returns the expected QMovie object.
    """
    result = mu.resources.load_movie("splash_screen")
    assert isinstance(result, QMovie)


def test_stylesheet():
    """
    Ensure the load_stylesheet function returns the expected result.
    """
    assert mu.resources.load_stylesheet("day.css").startswith(
        "QToolBar, QToolButton {\n    background: transparent;\n    margin: 0;\n    padding: 0;\n}"
    )


def test_load_font_data():
    """
    Ensure font data can be loaded
    """
    assert mu.resources.load_font_data("SourceCodePro-Regular.otf").startswith(
        b"OTTO\x00\x0f\x00\x80\x00\x03\x00pBASEe\x1e]\xbd\x00\x01\xb2$\x00\x00\x00FCFF W\x92{"
    )
