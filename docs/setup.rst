Developer Setup
===============

The source code is hosted on GitHub. Fork the repository with the following
command::

  git clone https://github.com/blackteahamburger/mu.git

You should use Python 3.9 or above.

Windows, OSX, Linux
+++++++++++++++++++

Create a working development environment by installing all the dependencies
into your virtualenv with::

    pip install -e ".[dev]"

.. note::

    The Mu package distribution, as specified in ``pyproject.toml``, declares
    both runtime and extra dependencies.

    The above mentioned ``pip install -e ".[dev]"`` installs all runtime
    dependencies and most development ones: it should serve nearly everyone.


.. warning::

    Sometimes, having several different versions of PyQt installed on your
    machine can cause problems (see
    `this issue <https://github.com/mu-editor/mu/issues/297>`_ for example).

    Using a virtualenv will ensure your development environment is safely
    isolated from such problematic version conflicts.

    If in doubt, throw away your virtualenv and start again with a fresh
    install as per the instructions above.

    On Windows, use the venv module from the standard library to avoid an
    issue with the Qt modules missing a DLL::

        py -3 -mvenv .venv

    Virtual environment setup can vary depending on your operating system.
    To learn more about virtual environments, see this `in-depth guide from Real Python <https://realpython.com/python-virtual-environments-a-primer/>`_.


Running Development Mu
++++++++++++++++++++++

.. note:: From this point onwards, instructions assume that you're using
   a virtual environment.

To run the local development version of Mu, in the root of the repository type::

  python run.py


Using ``make``
++++++++++++++

There is a Makefile that helps with most of the common workflows associated
with development. Typing ``make`` on its own will list the options.

Everything should be working if you can successfully run::

  make check

(You'll see the results from various code quality tools, the test suite and
code coverage.)

.. warning::

    In order to use the MicroPython REPL via USB serial you may need to add
    yourself to the ``dialout`` group on Linux.

Before Submitting
+++++++++++++++++

Before contributing code please make sure you've read :doc:`contributing` and
follow the checklist for contributing changes. We expect everyone participating
in the development of Mu to act in accordance with the PSF's
:doc:`code_of_conduct`.
