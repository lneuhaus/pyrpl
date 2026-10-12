"""
This package defines all the widgets to control the different modules of pyrpl.
Each Module instance can have a widget created by the function create_widget().
All module widgets inherit from the base class ModuleWidget. The class
member ModuleClass._widget_class specifies which ModuleWidget class should
be used for the particular ModuleClass.
"""

from .asg_widget import AsgWidget
from .base_module_widget import ModuleWidget, ReducedModuleWidget
from .cordic_widget import CordicWidget
from .curve_viewer_widget import CurveViewerWidget
from .iir_widget import IirWidget
from .iq_widget import IqWidget
from .lockbox_widget import (
    InputsWidget,
    LockboxInputWidget,
    LockboxSequenceWidget,
    LockboxStageWidget,
    LockboxWidget,
    OutputSignalWidget,
    StageOutputWidget,
)
from .module_manager_widget import (
    AsgManagerWidget,
    CordicManagerWidget,
    IirManagerWidget,
    IqManagerWidget,
    ModuleManagerWidget,
    PidManagerWidget,
    PwmManagerWidget,
    ScopeManagerWidget,
)
from .na_widget import NaWidget
from .pid_widget import PidWidget
from .pwm_widget import PwmWidget
from .pyrpl_config_widget import PyrplConfigWidget
from .scope_widget import ScopeWidget
from .signal_plotter_widget import SignalPlotterWidget
from .spec_an_widget import SpecAnWidget
