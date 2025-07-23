# -*- coding: utf-8 -*-
"""
Tests for the resources sub-module.
"""

from pathlib import Path
from unittest import mock

from PyQt6.QtGui import QIcon, QMovie, QPixmap

import mu.resources


def test_path_default():
    """
    Ensure the path function returns the expected result with default arguments.
    """
    mock_resources = Path("bar")
    with mock.patch.object(
        mu.resources, "importlib_files", return_value=mock_resources
    ):
        expected = str(mock_resources.joinpath("images", "foo"))
        assert mu.resources.path("foo") == expected


def test_path_custom_dir_ext():
    """
    Ensure the path function returns the expected result with custom resource_dir and ext.
    """
    mock_resources = Path("bar")
    with mock.patch.object(
        mu.resources, "importlib_files", return_value=mock_resources
    ):
        expected = str(mock_resources.joinpath("fonts", "font.ttf"))
        assert (
            mu.resources.path("font", resource_dir="fonts", ext=".ttf")
            == expected
        )


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
    result = mu.resources.load_stylesheet("day.css")
    assert isinstance(result, str)
    assert "QWidget" in result


def test_load_font_data():
    """
    Ensure font data can be loaded
    """
    data = mu.resources.load_font_data("SourceCodePro-Regular.otf")
    assert isinstance(data, bytes)
    assert len(data) > 0
