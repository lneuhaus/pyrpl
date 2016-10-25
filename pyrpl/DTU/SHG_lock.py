# Code in this file make a RedPitaya device into 2 channel interferometer lock, which can lock to arbitrary phase.
#
import os
import sys
import numpy as np
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph.console
import time
#
from ..redpitaya import RedPitaya
from ..gui import ScopeWidget, AllAsgGui, PidGui, IqWidget
from ..memory import MemoryTree
#
APP = QtGui.QApplication.instance()
#####
class SHGLock():
    def __init__(self, config='SHG_default'):
        _configdir = os.path.join(os.path.dirname(__file__), "i_config")
        self._configfile = os.path.join(_configdir, config + '.yml')
        self.c = MemoryTree(self._configfile)
        self.rp = RedPitaya(**self.c.redpitayas.catlab3._dict)
        time.sleep(2)
        #self.rp1 = RedPitaya(**self.c.redpitayas.catlab2._dict)
        self.setup_rp()
    # all useful rp modules are renamed here to better understand the function
        self.scan = self.rp.asg1
        self.bias = self.rp.asg2
        self.iq = self.rp.iq0
        self.pid = self.rp.pid0
    # start GUI and link the rp to the GUI
        #self.GUI=rp_SHGLock_GUI(_console_ns={'l': self}, _rp=self.rp, another_rp=self.rp1)
        self.GUI = rp_SHGLock_GUI(_console_ns={'l': self}, _rp=self.rp)
        sys.exit(APP.exec_())


    #
    def setup_rp(self):
        # setup up from config file
        _config_asg = self.c.rp_mod_connection.asg
        _config_pid = self.c.rp_mod_connection.pid
        _config_iq = self.c.rp_mod_connection.iq
        self.setup_asg(**_config_asg._dict)
        self.setup_pid(**_config_pid._dict)
        self.setup_iq(**_config_iq._dict)
    #
    def setup_asg(self, waveform, frequency, amplitude, offset, output_direct):
        self.rp.asg1.setup(waveform=waveform['asg1'],
                           frequency=frequency['asg1'],
                           amplitude=amplitude['asg1'],
                           offset=offset['asg1'],
                           output_direct=output_direct['asg1'])
        self.rp.asg2.setup(waveform=waveform['asg2'],
                           frequency=frequency['asg2'],
                           amplitude=amplitude['asg2'],
                           offset=offset['asg2'],
                           output_direct=output_direct['asg2'])
    #
    def setup_pid(self, input, output_direct):
        self.rp.pid0.input = input['pid0']
        self.rp.pid1.input = input['pid1']
        self.rp.pid2.input = input['pid2']
        self.rp.pid3.input = input['pid3']
        self.rp.pid0.output_direct = output_direct['pid0']
        self.rp.pid1.output_direct = output_direct['pid1']
        self.rp.pid2.output_direct = output_direct['pid2']
        self.rp.pid3.output_direct = output_direct['pid3']
    #
    def setup_iq(self, input, output_direct, output_signal, PDH_parameter):
        self.rp.iq1.input = input['iq1']
        self.rp.iq1.output_direct = output_direct['iq1']
        self.rp.iq0.setup(frequency=PDH_parameter['demodulation_frequency'],
                          bandwidth=PDH_parameter['LPF_frequency'],
                          gain=0.0,
                          phase=PDH_parameter['mixing_phase'],
                          acbandwidth=PDH_parameter['HPF_frequency'],
		                  amplitude=1,
                          input=input['iq1'],
                          output_direct=output_direct['iq0'],
                          output_signal=output_signal['iq0'],
                          quadrature_factor=1)


class rp_SHGLock_GUI(QtGui.QMainWindow):
    def __init__(self, _console_ns=None, _rp=None, another_rp=None):
        super(rp_SHGLock_GUI, self).__init__()
        self.setWindowTitle("SHG Lock for Teleportation Experiment")
        self.console_ns=_console_ns
        self.rp=_rp
        self.another_rp=another_rp
        # a scope
        self.scope_widget=SHG_Scope(name="SHG",
                                      rp=_rp,
                                      parent=None,
                                      module=self.rp.scope
                                      )
        # add a console with namespace contain SHGLock instance
        self.console_widget = pyqtgraph.console.ConsoleWidget(namespace=_console_ns)
        # a ASG controller for "asg1" scan and "asg2" bias
        self.asg_widget = AllAsgGui(parent=None, rp=self.rp)
        # a PID controller for "pid0" here
        self.pid_widget = PidGui(name="pid0",
                                 rp=self.rp,
                                 parent=None,
                                 module=getattr(self.rp, "pid0")
                                 )
        # a IQ controller for "iq0" here
        self.iq_widget = IqWidget(name="iq0",
                                  rp=self.rp,
                                  parent=None,
                                  module=getattr(self.rp, "iq0")
                                  )
        # setup controller layout here
        self.control_widget_layout = QtGui.QVBoxLayout()
        self.control_widget_layout.addWidget(self.asg_widget)
        self.control_widget_layout.addWidget(self.scope_widget)
        self.control_widget_layout.addWidget(self.pid_widget)
        self.control_widget_layout.addWidget(self.iq_widget)
        #
        self.control_widget=QtGui.QWidget()
        self.control_widget.setLayout(self.control_widget_layout)
        #------------#
        # a scope for another rp
        '''
        self.another_scope_widget = ScopeWidget(name="another_SHG",
                                                rp=another_rp,
                                                parent=None,
                                                module=self.another_rp.scope
                                                )
        '''
        # set dock_widgets for the main windows
        self.dock_widgets = {}
        self.last_docked = None
        self.add_dock_widget(self.console_widget,'console')
        self.add_dock_widget(self.control_widget,'controller')
        #self.add_dock_widget(self.another_scope_widget, 'another')
        #---------------------------#
        # setup timer and run the GUI
        self.gui_timer = QtCore.QTimer()
        self.run_gui()

    def add_dock_widget(self, widget, name):
        dock_widget = QtGui.QDockWidget(name)
        dock_widget.setObjectName(name)
        dock_widget.setFeatures(
            QtGui.QDockWidget.DockWidgetFloatable |
            QtGui.QDockWidget.DockWidgetMovable |
            QtGui.QDockWidget.DockWidgetVerticalTitleBar)
        self.dock_widgets[name] = dock_widget
        dock_widget.setWidget(widget)
        self.addDockWidget(QtCore.Qt.TopDockWidgetArea,dock_widget)
        if self.last_docked is not None:
            self.tabifyDockWidget(self.last_docked, dock_widget)
        self.last_docked = dock_widget

    def run_gui(self):
        """
        Opens the graphical user interface.
        """
        self.show()
        self.scope_widget.run_continuous()

class SHG_Scope(ScopeWidget):
    def save(self):
        self.stop()
        _duration = self.module.duration
        _n = self.module.data_length
        _t_array = np.linspace(0,_n-1,_n)*(_duration)/(_n-1)
        _ch1_array = self.datas[0]
        _ch2_array = self.datas[1]
        np.savetxt('t.txt', _t_array)
        np.savetxt('ch1.txt', _ch1_array)
        np.savetxt('ch2.txt', _ch2_array)



