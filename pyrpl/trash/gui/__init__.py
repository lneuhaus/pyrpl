import logging
logger = logging.getLogger(name=__name__)

# do not oblige the user to install all packages required for the gui
try:
    from .redpitaya_gui import RedPitayaGui
except:
    logger.warning("Could not import gui. Please make sure that all "\
                   +"necessary packages are installed")
from .redpitaya_gui import RedPitayaGui
