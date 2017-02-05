from .interferometer import *
from .fabryperot import *
from .linear import *
#from .fabryperotmembranes import *
#from .interferometer_am import *
#from .lmsd import *
#from .tilt import *

# try to import user models if applicable
try:
    from pyrpl import user_model_dir
    import sys, os
    sys.path.append(user_model_dir)
    for module in os.listdir(user_model_dir):
        if module == '__init__.py' or module[-3:] != '.py':
            continue
        __import__(module[:-3], locals(), globals(), [], -1)
        logger.debug("Loaded custom user models from %s"%module)
    del module
except:
    logger.warning("An error occured during the import of user model files!")
