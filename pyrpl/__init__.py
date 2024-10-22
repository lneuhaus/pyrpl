from ._version import __version_info__, __version__

__author__ = "Leonhard Neuhaus <neuhaus@lkb.upmc.fr>"
__license__ = "MIT License"

# manage warnings of numpy and scipy
import warnings
import numpy as np
# pyqtgraph is throwing a warning on ScatterPlotItem
try:
    warnings.simplefilter("ignore", np.exceptions.VisibleDeprecationWarning)
    warnings.simplefilter("error", np.exceptions.ComplexWarning)
except AttributeError:
    warnings.simplefilter("ignore", np.VisibleDeprecationWarning)
    warnings.simplefilter("error", np.ComplexWarning)
    
# former issue with IIR, now resolved
#from scipy.signal import BadCoefficients
#warnings.simplefilter("error", BadCoefficients)

#set up loggers
import logging
logging.basicConfig()
logger = logging.getLogger(name=__name__)
# only show errors or warnings until userdefine log level is set up
logger.setLevel(logging.INFO)

# enable ipython QtGui support if needed
try:
    from IPython import get_ipython
    IPYTHON = get_ipython()
    IPYTHON.run_line_magic("gui","qt")
except BaseException as e:
    logger.debug('Could not enable IPython gui support: %s.' % e)

# get QApplication instance
from qtpy import QtCore, QtWidgets
APP = QtWidgets.QApplication.instance()
if APP is None:
    logger.debug('Creating new QApplication instance "pyrpl"')
    APP = QtWidgets.QApplication(['pyrpl'])

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
        os.mkdir(path)  # pragma: no cover

# try to set log level (and automatically generate custom global_config file)
from .pyrpl_utils import setloglevel
from .memory import MemoryTree
global_config = MemoryTree('global_config', source='global_config')
try:
    setloglevel(global_config.general.loglevel, loggername=logger.name)
except:  # pragma: no cover
    pass

# main imports
from .redpitaya import RedPitaya
from .hardware_modules import *
from .attributes import *
from .modules import *
from .curvedb import *
from .pyrpl import *
