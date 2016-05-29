__version__ = "0.9.0.0"

# set up the logging level at the root module
import logging
#logging.getLogger(name=__name__).setLevel(logging.DEBUG)
logging.getLogger(name=__name__).setLevel(logging.INFO) # normal setting

from redpitaya import RedPitaya
from redpitaya_modules import *
from registers import *
#from pyrpl import Pyrpl
