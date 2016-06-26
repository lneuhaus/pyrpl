import logging
logger = logging.getLogger(name=__name__)


def getmodel(modeltype):
    try:
        return globals()[modeltype]
    except KeyError:
        # try to find a similar model with lowercase spelling
        for k in globals():
            if k.lower() == modeltype.lower():
                return globals()[k]
        logger.error("Model %s not found in model definition file %s",
                     modeltype, __file__)


class Model(object):
    " generic model object that will make smart use of its inputs and outputs"
    state = {'theoretical': {},
             'experimental': {},
             'set': {}}
    inputs = {}
    outputs = {}

    def __init__(self, parent=None):
        self.logger = logging.getLogger(__name__)
        if parent is None:
            self._parent = self
        else:
            self._parent = parent
        self._config = self._parent.c.model

    def setup(self):
        pass

    def search(self, *args, **kwargs):
        pass

    def lock(self, *args, **kwargs):
        pass


class Interferometer(Model):
    def reflection(self, variable):
        return variable

    pass


class FabryPerot(Model):
    pass


