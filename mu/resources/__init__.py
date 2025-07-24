"""
Copyright (c) 2015-2017 Nicholas H.Tollervey and others (see the AUTHORS file).

Based upon work done for Puppy IDE by Dan Pope, Nicholas Tollervey and Damien
George.

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

import os
from importlib.resources import files as importlib_files

from PyQt6.QtCore import QDir
from PyQt6.QtGui import QIcon, QPixmap

# The following lines add the images and css directories to the search path.
QDir.addSearchPath(
    "images", str(importlib_files("mu.resources").joinpath("images"))
)
QDir.addSearchPath("css", str(importlib_files("mu.resources").joinpath("css")))


def path(name, resource_dir="images"):
    """Return the filename for the referenced image."""
    return importlib_files("mu.resources").joinpath(resource_dir, name)


def load_icon(name):
    """Load an icon from the resources directory."""
    svg_path = str(path(name + ".svg"))
    if os.path.exists(svg_path):
        svg_icon = QIcon(svg_path)
        if svg_icon:
            return svg_icon
    return QIcon(str(path(name)))


def load_pixmap(name, size=None):
    """Load a pixmap from the resources directory."""
    if size is not None:
        icon = load_icon(name)
        return icon.pixmap(size)
    return QPixmap(str(path(name)))


def load_stylesheet(name):
    """Load a CSS stylesheet from the resources directory."""
    return path(name, "css").read_bytes().decode("utf8")


def load_font_data(name):
    """
    Load the (binary) content of a font as bytes
    """
    return path(name, "fonts").read_bytes()
