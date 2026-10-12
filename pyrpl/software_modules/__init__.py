from ..modules import Module
from ..pyrpl_utils import all_subclasses
from .curve_viewer import CurveViewer
from .lockbox import (
    AdditionalFilterAttribute,
    CalibrationData,
    GainOptimizer,
    InputDirect,
    InputFromOutput,
    InputIq,
    InputSignal,
    InsufficientResourceError,
    IqFilterProperty,
    IqQuadratureFactorProperty,
    Lockbox,
    LockboxLoop,
    LockboxModule,
    LockboxModuleDictProperty,
    LockboxPlotLoop,
    OutputSignal,
    PiezoOutput,
    Signal,
)
from .loop import Loop, PlotLoop, PlotWindow
from .module_managers import (
    Asgs,
    Cordics,
    Hks,
    Iirs,
    Iqs,
    ModuleManager,
    Pids,
    Pwms,
    Scopes,
    Trigs,
)
from .network_analyzer import NetworkAnalyzer
from .pyrpl_config import PyrplConfig
from .signal_plotter import SignalPlotter
from .software_pid import RunningProperty, SoftwarePidController, SoftwarePidLoop
from .spectrum_analyzer import SpectrumAnalyzer


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
    raise ModuleNotFound(
        f"class {name} not found in subclasses of Module. Did you forget to import a custom module?"
    )


__all__ = [
    "Module",
    "Asgs",
    "Cordics",
    "Iqs",
    "Pids",
    "Scopes",
    "Iirs",
    "Pwms",
    "Hks",
    "Trigs",
    "ModuleManager",
    "InsufficientResourceError",
    "NetworkAnalyzer",
    "SpectrumAnalyzer",
    "PyrplConfig",
    "CurveViewer",
    "SignalPlotter",
    "ModuleNotFound",
    "get_module",
    "LockboxModule",
    "LockboxModuleDictProperty",
    "LockboxLoop",
    "LockboxPlotLoop",
    "CalibrationData",
    "Signal",
    "InputDirect",
    "InputSignal",
    "InputFromOutput",
    "IqQuadratureFactorProperty",
    "IqFilterProperty",
    "InputIq",
    "AdditionalFilterAttribute",
    "OutputSignal",
    "PiezoOutput",
    "Lockbox",
    "GainOptimizer",
    "Loop",
    "PlotLoop",
    "PlotWindow",
    "RunningProperty",
    "SoftwarePidController",
    "SoftwarePidLoop",
]
