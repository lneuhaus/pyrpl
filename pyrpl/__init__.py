__version__ = "0.9.0.0"

#__all__ = ["registers", "curvedb", "redpitaya", "hardware_modules", "iir",
#           "memory", "pyrpl", "signal", "model"]


# set up the logging level at the root module as configured in 'config/global_config.yml'
import warnings
import numpy as np
from scipy.signal import BadCoefficients
warnings.simplefilter("ignore", np.VisibleDeprecationWarning) # pyqtgraph is throwing a warning on ScatterPlotItem
warnings.simplefilter("error", np.ComplexWarning) # pyqtgraph is throwing a warning on ScatterPlotItem
warnings.simplefilter("error", BadCoefficients)

import logging
logging.basicConfig()
logger = logging.getLogger(name=__name__)
logger.setLevel(logging.ERROR)  # only show errors until userdefine log level is set up

import os

# get user directory
try:  # first try from environment variable
    user_dir = os.environ["PYRPL_USER_DIR"]
except KeyError:  # otherwise, try ~/pyrpl_user_dir (where ~ is the user's home dir)
    user_dir = os.path.expanduser('~/pyrpl_user_dir')

# make variable directories
user_config_dir = os.path.join(user_dir, 'config')
user_curve_dir = os.path.join(user_dir, 'curve')
user_lockbox_dir = os.path.join(user_dir, 'lockbox')
default_config_dir = os.path.join(os.path.dirname(__file__), 'config')
# create dirs if necessary
for path in [user_dir, user_config_dir, user_curve_dir, user_lockbox_dir]:
    if not os.path.isdir(path):
        os.mkdir(path)

# try to set log level (and automatically generate custom global_config file
from .pyrpl_utils import setloglevel
from .memory import MemoryTree
global_config = MemoryTree('global_config', source='global_config')
try:
    setloglevel(global_config.general.loglevel, loggername=logger.name)
except:
    pass

from .curvedb import CurveDB
from .redpitaya import RedPitaya
from .hardware_modules import *
from .attributes import *
from .modules import *
from .curvedb import *
from .pyrpl import *
