from ..modules import Module
from .module_managers import Asgs, Iqs, Pids, Scopes, Iirs, Pwms
from .network_analyzer import NetworkAnalyzer
from .spectrum_analyzer import SpectrumAnalyzer
from .pyrpl_config import PyrplConfig
from .curve_viewer import CurveViewer
from .lockbox import *
from .loop import *
from .software_pid import *
from .module_managers import *
from ..pyrpl_utils import all_subclasses


class ModuleNotFound(ValueError):
    pass

def get_module(name):
    """
    Returns the subclass of Module named name (if exists, otherwise None)
    """
    subclasses = all_subclasses(Module)
    for cls in subclasses:
        if cls.__name__ == name:
            return cls
    raise ModuleNotFound("class %s not found in subclasses of Module. Did you "
                         "forget to import a custom module?"%name)
