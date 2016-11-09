__version__ = "0.9.0.0"

#__all__ = ["registers", "curvedb", "redpitaya", "hardware_modules", "iir",
#           "memory", "pyrpl", "signal", "model"]

# set up the logging level at the root module
import logging
#logging.getLogger(name=__name__).setLevel(logging.INFO)
logging.getLogger(name=__name__).setLevel(logging.DEBUG) # for debugging


from .curvedb import CurveDB
from .redpitaya import RedPitaya
from .hardware_modules import *
from .attributes import *
from .curvedb import *
from .pyrpl import *

