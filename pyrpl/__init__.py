__version__ = "0.9.0.0"

#__all__ = ["registers", "curvedb", "redpitaya", "hardware_modules", "iir",
#           "memory", "pyrpl", "signal", "model"]


# set up the logging level at the root module as configured in 'config/global_config.yml'
import logging
logger = logging.getLogger(name=__name__)
logger.setLevel(logging.ERROR)  # only show errors until userdefine log level is set up
from . import pyrpl_utils
from .global_config import global_config
try:
    pyrpl_utils.setloglevel(global_config.general.loglevel, loggername=logger.name)
except:
    pass


from .curvedb import CurveDB
from .redpitaya import RedPitaya
from .hardware_modules import *
from .attributes import *
from .curvedb import *
from .pyrpl import *
