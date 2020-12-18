from .interferometer import *
from .fabryperot import *
from .linear import *
from .custom_lockbox_example import *
from .pll import *

# try to import user models if applicable
import sys, os
from .... import user_lockbox_dir
sys.path.append(user_lockbox_dir)

usermodels = []
module = None
try:
    for module in os.listdir(user_lockbox_dir):
        if module == '__init__.py' or module[-3:] != '.py':
            continue
        usermodels.append(__import__(module[:-3], locals(), globals(), [], 0))
        logger.debug("Custom user models from %s were successfully imported!"%module)
    del module
except KeyError:
    logger.warning("An error occured during the import of user model files! "
                   "The exception occured during the import of module '%s'. ",
                   module)
    raise