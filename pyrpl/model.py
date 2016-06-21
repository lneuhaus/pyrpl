import logging



def getmodel(type):
    return globals()[type]

class Model(object):
    " general model object that will make smart use of  its inputs and outputs"
    state = { 'theoretical' : {},
              'experimental' : {},
              'set': {}}
    inputs = {}
    outputs = {}

    def __init__(self, parent):
        self._parent = parent
        self.logger = logging.getLogger(self.__name__)

    def setup(self):
        pass

    def search(self, *args, **kwargs):
        pass

    def lock(self, *args, **kwargs):
        pass

class Interferometer(Model):
    pass

class FabryPerot(Model):
    pass

