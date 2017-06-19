__version__ = "0.9.0.0"

#__all__ = ["registers", "curvedb", "redpitaya", "hardware_modules", "iir",
#           "memory", "pyrpl", "signal", "model"]

from ._version import __version_info__, __version__

__author__ = "Leonhard Neuhaus <neuhaus@lkb.upmc.fr>"
__license__ = "GNU General Public License 3 (GPLv3)"

# set up the logging level at the root module as configured in 'config/global_config.yml'
import warnings
import numpy as np
from scipy.signal import BadCoefficients
warnings.simplefilter("ignore", np.VisibleDeprecationWarning) # pyqtgraph is throwing a warning on ScatterPlotItem
warnings.simplefilter("error", np.ComplexWarning) # pyqtgraph is throwing a warning on ScatterPlotItem
warnings.simplefilter("error", BadCoefficients)

#set up loggers
import logging
logging.basicConfig()
logger = logging.getLogger(name=__name__)
# only show errors or warnings until userdefine log level is set up
logger.setLevel(logging.WARNING)

# enable ipython QtGui support if needed
try:
    from IPython import get_ipython
    IPYTHON = get_ipython()
    IPYTHON.magic("gui qt")
except BaseException as e:
    logger.warning('Could not enable IPython gui support: %s.' % e)

# get QApplication instance
from PyQt4 import QtCore, QtGui
APP = QtGui.QApplication.instance()
if APP is None:
    logger.warning('creating new QApplication instance "pyrpl"')
    APP = QtGui.QApplication(['pyrpl'])

# get user directories
import os
try:  # first try from environment variable
    user_dir = os.environ["PYRPL_USER_DIR"]
except KeyError:  # otherwise, try ~/pyrpl_user_dir (where ~ is the user's home dir)
    user_dir = os.path.join(os.path.expanduser('~'), 'pyrpl_user_dir')

# make variable directories
user_config_dir = os.path.join(user_dir, 'config')
user_curve_dir = os.path.join(user_dir, 'curve')
user_lockbox_dir = os.path.join(user_dir, 'lockbox')
default_config_dir = os.path.join(os.path.dirname(__file__), 'config')
# create dirs if necessary
for path in [user_dir, user_config_dir, user_curve_dir, user_lockbox_dir]:
    if not os.path.isdir(path):
        os.mkdir(path)

# try to set log level (and automatically generate custom global_config file)
from .pyrpl_utils import setloglevel
from .memory import MemoryTree
global_config = MemoryTree('global_config', source='global_config')
try:
    setloglevel(global_config.general.loglevel, loggername=logger.name)
except:
    pass

# main imports
from .redpitaya import RedPitaya
from .hardware_modules import *
from .attributes import *
from .modules import *
from .curvedb import *
from .pyrpl import *
