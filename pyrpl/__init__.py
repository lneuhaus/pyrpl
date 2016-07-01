__version__ = "0.9.0.0"

# set up the logging level at the root module
import logging
logging.getLogger(name=__name__).setLevel(logging.INFO)
#logging.getLogger(name=__name__).setLevel(logging.DEBUG) # for debugging


from .curvedb import CurveDB
from .redpitaya import RedPitaya
from .redpitaya_modules import *
from .registers import *
from .curvedb import *
from .pyrpl import *
