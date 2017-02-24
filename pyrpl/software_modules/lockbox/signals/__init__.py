from pyrpl.modules import SoftwareModule
from six import with_metaclass


class Signal(SoftwareModule):  # with_metaclass(NameAttributesMetaClass, object)
    """
    represention of a physial signal. Can be either an imput or output signal.
    """
    _widget = None
    pass

from .output import *
from .input import *