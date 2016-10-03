# Code in this file make a RedPitaya device into 2 channel interferometer lock, which can lock to arbitrary phase.
#
import os
import sys
import numpy as np
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph.console
#
from ..redpitaya import RedPitaya
from ..gui import ScopeWidget, AllAsgGui, PidGui, IqWidget
from ..memory import MemoryTree
#
APP = QtGui.QApplication.instance()
if APP is None:
    APP = QtGui.QApplication(["redpitaya_gui"])
#####
class SHGLock():
    def __init__(self, config='SHG_default'):
        _configdir = os.path.join(os.path.dirname(__file__), "i_config")
        self._configfile = os.path.join(_configdir, config + '.yml')
        self.c = MemoryTree(self._configfile)
        self.rp = RedPitaya(**self.c.redpitaya._dict)
        self.setup_rp()
    # all useful rp modules are renamed here to better understand the function
        self.scan = self.rp.asg1
        self.bias = self.rp.asg2
        self.iq = self.rp.iq0
        self.pid = self.rp.pid0
    # start GUI and link the rp to the GUI
        self.GUI=rp_SHGLock_GUI(_console_ns={'l': self}, _rp=self.rp)
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
    #
    def scan(self, calibrate=True):
        self.pid.output_direct='off'
        if calibrate == True:
            self.calibrate()
    #
    def fringe_to_fit(self, t, slope=0.15, T=103.0, phi_s=0, Imean=0.5, Iamp=0.3):
        _cyc = t // (T / 2)
        return Imean + Iamp * np.cos(
            (_cyc % 2 * T / 2 * slope + (-1) ** (_cyc % 2) * (t - T / 2 * _cyc) * slope + phi_s))
    #
    '''
    Calibrate a lock channel:
        (1) Set PID, IQ to zero;
        (2) Scan with sawtooth wave according to Config file. (with asg1 or asg2)
        (3) Get data from scope, which is used to fit the interferometer fringe
        (4) Fringe: defined in a lambda function inside calibrate methord
        (5) Set asg to zero
        (6) Return: max, min, fringe visibility , fitting accuricy
    '''
    def calibrate(self, ch=1, min_duration=0.1):
        # the duration of scope is not continuous, the real duration is accessed by: self.rp.scope.duration
        if not (ch==1 or ch==2):
            raise KeyError('Scope channel should be 1 or 2 with int type')
        _n=self.rp.scope.data_length
        _trig = 'immediately'
        _err_sig ={'1':'adc1','2':'adc2'}
        _scan = {'1':'dac1','2':'dac2'}
        self.rp.asg1.setup(waveform='ramp', frequency='37', amplitude=0.15, output_direct='out1')
        self.rp.scope.setup(duration=min_duration, trigger_source=_trig, input1=_err_sig[str(ch)], input2=_scan[str(ch)])
        _ch1_data=self.rp.scope.curve(1)
        _ch2_data=self.rp.scope.curve(2)
        _t= np.linspace(0,_n-1,_n)*self.rp.scope.duration/(_n-1)
        self.rp.asg1.setup(waveform='ramp', frequency='37', amplitude=0.3, output_direct='off')
        self.cal_result={'time':_t,'fringe':_ch1_data,'scan':_ch2_data}
    #
    def cal_txt(self):
        try:
            np.savetxt('t.txt', self.cal_result['time'])
            np.savetxt('f.txt', self.cal_result['fringe'])
            np.savetxt('s.txt', self.cal_result['scan'])
        except:
            pass

class rp_SHGLock_GUI(QtGui.QMainWindow):
    def __init__(self, _console_ns=None, _rp=None):
        super(rp_SHGLock_GUI, self).__init__()
        self.setWindowTitle("SHG Lock for Teleportation Experiment")
        self.console_ns=_console_ns
        self.rp=_rp
        # a scope
        self.scope_widget=ScopeWidget(name="SHG",
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
        # set dock_widgets for the main windows
        self.dock_widgets = {}
        self.last_docked = None
        self.add_dock_widget(self.console_widget,'console')
        self.add_dock_widget(self.control_widget,'controller')
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
        sys.exit(APP.exec_())