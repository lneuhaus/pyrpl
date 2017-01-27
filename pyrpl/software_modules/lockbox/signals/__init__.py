from pyrpl.modules import SoftwareModule
from six import with_metaclass


class Signal(SoftwareModule): # with_metaclass(NameAttributesMetaClass, object)
    """
    An input or output signal.
    """
    widget = None
    pass

from .output import *
from .input import *