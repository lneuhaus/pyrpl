from ..modules import SoftwareModule
from .module_managers import AsgManager, IqManager, PidManager, ScopeManager, IirManager
from .network_analyzer import NetworkAnalyzer
from .spectrum_analyzer import SpectrumAnalyzer
from .lockbox import Lockbox


def all_subclasses(cls):
    """returns a list containing all subclasses of cls (recursively)"""
    # see http://stackoverflow.com/questions/3862310/how-can-i-find-all-subclasses-of-a-class-given-its-name
    return cls.__subclasses__() + [g for s in cls.__subclasses__()
                                   for g in all_subclasses(s)]

class SoftwareModuleNotFound(ValueError):
    pass

def get_software_module(name):
    """
    Returns the subclass of SoftwareModule named name (if exists, otherwise None)
    """
    subclasses = all_subclasses(SoftwareModule)
    for cls in subclasses:
        if cls.__name__ == name:
            return cls
    raise SoftwareModuleNotFound("class %s not found in subclasses of SoftwareModule. Did you forget to import a custom"
                                 "module."%name)
