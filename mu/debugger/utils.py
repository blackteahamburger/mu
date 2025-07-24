"""
Debug related utility functions for the Mu editor.

Copyright (c) Nicholas H.Tollervey and others (see the AUTHORS file).

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

import tokenize
from io import StringIO


def is_breakpoint_line(code):
    """
    Return a boolean indication if the specified code from a single line can
    have a breakpoint added to it.

    Based entirely on simple but effective heuristics (see comments).
    """
    code = code.strip()
    if not code:
        return False
    # More robust detection for comments and blank lines
    try:
        tokens = list(tokenize.generate_tokens(StringIO(code).readline))
        # If there is only one token and its type is COMMENT or NL, it's a comment or blank line
        if len(tokens) == 1 and tokens[0].type in (
            tokenize.COMMENT,
            tokenize.NL,
        ):
            return False
        # If the first token is a comment, cannot set breakpoint
        if tokens[0].type == tokenize.COMMENT:
            return False
        # If the first token is a string (possibly a docstring), cannot set breakpoint
        if tokens[0].type == tokenize.STRING:
            return False
    except tokenize.TokenError:
        return False
    # Can't set breakpoints on lines that end with opening (, { or [
    if code[-1] in ("(", "{", "["):
        return False
    # Can't set breakpoints on lines that contain only closing ), } or ]
    if len(code) == 1 and code in (")", "}", "]"):
        return False
    return True
