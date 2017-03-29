"""
This package defines all the widgets to control the different modules of pyrpl.
"""

from .base_module_widget import ReducedModuleWidget, ModuleWidget
from .asg_widget import AsgWidget
from .iir_widget import IirWidget
from .iq_widget import IqWidget
from .lockbox_widget import LockboxWidget, OutputSignalWidget, InputsWidget, \
                            LockboxInputWidget, LockboxSequenceWidget, LockboxStageWidget, StageOutputWidget
from .module_manager_widget import ModuleManagerWidget, IqManagerWidget, PidManagerWidget, ScopeManagerWidget, \
                                    IirManagerWidget, AsgManagerWidget
from .na_widget import NaWidget
from .pid_widget import PidWidget
from .scope_widget import ScopeWidget
from .spec_an_widget import SpecAnWidget
from .pyrpl_config_widget import PyrplConfigWidget
from .curve_viewer_widget import CurveViewerWidget