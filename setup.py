import os
import re
from setuptools import setup


base_dir = os.path.dirname(__file__)


DUNDER_ASSIGN_RE = re.compile(r"""^__\w+__\s*=\s*['"].+['"]$""")
about = {}
with open(os.path.join(base_dir, "mu", "__init__.py"), encoding="utf8") as f:
    for line in f:
        if DUNDER_ASSIGN_RE.search(line):
            exec(line, about)

with open(os.path.join(base_dir, "README.rst"), encoding="utf8") as f:
    readme = f.read()

with open(os.path.join(base_dir, "CHANGES.rst"), encoding="utf8") as f:
    changes = f.read()


install_requires = [
    #
    # The core 'install_requires' should only be things
    # which are needed for the main editor to function.
    #
    "PyQt6>=6.3.1"
    + ';"arm" not in platform_machine and "aarch" not in platform_machine',
    "PyQt6-QScintilla>=2.13.3"
    + ';"arm" not in platform_machine and "aarch" not in platform_machine',
    "PyQt6-Charts>=6.3.1"
    + ';"arm" not in platform_machine and "aarch" not in platform_machine',
    "jupyter-client",
    # ipykernel v5.5.6 resolves issue ipython/ipykernel#759.
    "ipykernel>=5.5.6",
    "qtconsole~=5.4",
    # adafruit-board-toolkit is used to find serial ports and help identify
    # CircuitPython boards in the CircuitPython mode.
    "adafruit-board-toolkit~=1.1",
    "pyserial~=3.5",
    # `flake8` is actually a testing/packaging dependency that, among other
    # packages, brings in `pycodestyle` and `pyflakes` which are runtime
    # dependencies. For the sake of "locality", it is being declared here,
    # though. Regarding these packages' versions, please refer to:
    # http://flake8.pycqa.org/en/latest/faq.html#why-does-flake8-use-ranges-for-its-dependencies
    "flake8 >= 3.8.3",
    "black>=19.10b0",
    "platformdirs>=2.0.0",
    "semver>=2.8.0",
    # Needed to deploy from web mode
    "requests>=2.0.0",
    "pgzero>=1.2.1",
    "flask>=2.0.3",
    "esptool>=3",
    "microfs>=1.4.6",
    "uflash>=2.1.0",
    #
    # Needed to resolve an issue with paths in the user virtual environment
    #
    "pywin32; sys_platform=='win32'",
]


extras_require = {
    "tests": [
        "pytest>=5",
        "pytest-cov",
        "pytest-random-order>=1.0.0",
        "pytest-timeout",
        "coverage",
    ],
    "docs": ["sphinx"],
    "package": [
        # Wheel building and PyPI uploading
        "wheel",
        "twine",
    ],
    "i18n": ["babel"],
    "utils": ["scrapy", "beautifulsoup4", "requests"],
}

extras_require["dev"] = (
    extras_require["tests"]
    + extras_require["docs"]
    + extras_require["package"]
    + extras_require["i18n"]
)

extras_require["all"] = list({
    req for extra, reqs in extras_require.items() for req in reqs
})


setup(
    name=about["__title__"],
    version=about["__version__"],
    description=about["__description__"],
    long_description="{}\n\n{}".format(readme, changes),
    author=about["__author__"],
    author_email=about["__email__"],
    url=about["__url__"],
    license=about["__license__"],
    packages=[
        "mu",
        "mu.modes",
        "mu.debugger",
        "mu.interface",
        "mu.modes.api",
        "mu.locale.de_DE.LC_MESSAGES",
        "mu.locale.es.LC_MESSAGES",
        "mu.locale.fr.LC_MESSAGES",
        "mu.locale.ja.LC_MESSAGES",
        "mu.locale.nl.LC_MESSAGES",
        "mu.locale.pl.LC_MESSAGES",
        "mu.locale.pt_BR.LC_MESSAGES",
        "mu.locale.pt_PT.LC_MESSAGES",
        "mu.locale.ru_RU.LC_MESSAGES",
        "mu.locale.sk_SK.LC_MESSAGES",
        "mu.locale.sv.LC_MESSAGES",
        "mu.locale.uk_UA.LC_MESSAGES",
        "mu.locale.vi.LC_MESSAGES",
        "mu.locale.zh_CN.LC_MESSAGES",
        "mu.resources",
        "mu.resources.css",
        "mu.resources.fonts",
        "mu.resources.images",
        "mu.resources.pygamezero",
        "mu.resources.web.static.css",
        "mu.resources.web.static.img",
        "mu.resources.web.templates",
    ],
    python_requires=">=3.9",
    install_requires=install_requires,
    extras_require=extras_require,
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Win32 (MS Windows)",
        "Environment :: X11 Applications :: Qt",
        "Environment :: MacOS X",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: POSIX",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Education",
        "Topic :: Games/Entertainment",
        "Topic :: Software Development",
        "Topic :: Software Development :: Debuggers",
        "Topic :: Software Development :: Embedded Systems",
        "Topic :: Text Editors",
        "Topic :: Text Editors :: Integrated Development Environments (IDE)",
    ],
    entry_points={"console_scripts": ["mu-editor = mu.app:run"]},
)
