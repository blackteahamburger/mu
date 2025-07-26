import os

import platformdirs

# The default directory for application data (i.e., configuration).
DATA_DIR = platformdirs.user_data_dir(appname="mu", appauthor="python")

# Maximum line length for using both in Check and Tidy
MAX_LINE_LENGTH = 79

# The user's home directory.
HOME_DIRECTORY = os.path.expanduser("~")

# Name of the directory within the home folder to use by default
WORKSPACE_NAME = "mu_code"
