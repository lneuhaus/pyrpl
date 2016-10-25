from .SHG_lock import *
import numpy as np
from pyqtgraph.Qt import QtGui, QtCore
import time
import logging
class SHGAutolock(SHGLock, QtCore.QObject):


    inform_bias_changed = QtCore.pyqtSignal()
    send_DC_value = QtCore.pyqtSignal(float)
    stop_autolock = QtCore.pyqtSignal()

    def __init__(self, config='SHG_default'):
        self.logger = logging.getLogger(name=__name__)
        QtCore.QObject.__init__(self)
        self.cal_data={'max': 0.4, 'min':0}
        self.autolocker=SHGAutolocker()
        self.autolocker_thread=QtCore.QThread()
        self.autolocker.moveToThread(self.autolocker_thread)
        # started is a signal of Qthread, while start is a slot of Qthread
        #
        self.autolocker_thread.started.connect(self.autolocker.run_auto_lock)
        #
        self.autolocker.give_bias.connect(self.change_rp_bias)
        self.inform_bias_changed.connect(self.autolocker.change_wait_flag)
        #
        self.autolocker.ask_DC.connect(self.response_ask_DC)
        self.send_DC_value.connect(self.autolocker.renew_DC)
        #
        self.autolocker.start_pid.connect(self.rp_start_pid)
        #
        self.stop_autolock.connect(self.autolocker_thread.quit)
        SHGLock.__init__(self,config=config)

    #

    def change_rp_bias(self, bias=0):
        self.bias.offset = bias
        self.inform_bias_changed.emit()
    #

    def response_ask_DC(self):
        DC_value=self.GUI.scope_widget.datas[0].mean()
        self.send_DC_value.emit(DC_value)
    #

    def rp_start_pid(self, pid_list=[0,0,0]):
        self.pid.i=0
        self.pid.ival=0
        time.sleep(0.01)
        self.pid.output_direct='out1'
        self.pid.p=pid_list[0]
        self.pid.i=pid_list[1]
        self.pid.d=pid_list[2]
        self.stop_autolock.emit()

    #
    @property
    def scan_on(self, calibrate=True):
        self.pid.output_direct='off'
        self.scan.setup(waveform='ramp',amplitude=0.8,offset=0,frequency=37,output_direct='out1')
        if calibrate == True:
            return self.calibrate()
        else:
            return self.scan.amplitude

    @property
    def scan_off(self, calibrate=True):
        self.scan.output_direct='off'
        return 'scan off'
    #
    def autoPDHlock(self):
        self.bias.offset=0
        self.scan_off
        self.autolocker_thread.start()
    @property
    def pid_on(self):
        self.pid.p=0.1
        self.pid.i=0
        self.pid.d=0
        self.pid.ival=0
        self.pid.setpoint=0
        self.pid.output_direct='out1'
        time.sleep(1)
        self.pid.i=1
        return 'pid on'
    #
    def fringe_to_fit(self, t, slope=0.15, T=103.0, phi_s=0, Imean=0.5, Iamp=0.3):
        _cyc = t // (T / 2)
        return Imean + Iamp * np.cos(
            (_cyc % 2 * T / 2 * slope + (-1) ** (_cyc % 2) * (t - T / 2 * _cyc) * slope + phi_s))
    #
    def calibrate(self):
        # the duration of scope is not continuous, the real duration is accessed by: self.rp.scope.duration
        max_data=[]
        min_data=[]
        #_n=self.rp.scope.data_length
        for i in range(5):
            self.rp.scope.setup(duration=0.1, trigger_source='immediately', input1='adc1', input2='dac1')
            _ch1_data=self.rp.scope.curve(1)
            max_data.append(_ch1_data.max())
            min_data.append(_ch1_data.min())
        #_ch2_data=self.rp.scope.curve(2)
        #_t= np.linspace(0,_n-1,_n)*(self.rp.scope.duration)/(_n-1)
        #self.rp.asg1.setup(waveform='ramp', frequency='37', amplitude=0.3, output_direct='off')
        #self.cal_data={'time':_t,'fringe':_ch1_data,'scan':_ch2_data}
        self.cal_data={'max': np.mean(max_data), 'min':np.mean(min_data)}
        return self.cal_data
    #
    def cal_txt(self):
        try:
            np.savetxt('t.txt', self.cal_result['time'])
            np.savetxt('f.txt', self.cal_result['fringe'])
            np.savetxt('s.txt', self.cal_result['scan'])
        except:
            pass


class SHGAutolocker(QtCore.QObject):

    give_bias=QtCore.pyqtSignal(float)
    ask_DC=QtCore.pyqtSignal()
    start_pid=QtCore.pyqtSignal(list)

    def __init__(self):
        self.logger = logging.getLogger(name=__name__)
        super(SHGAutolocker,self).__init__()
        self.wait_flag=True

    @QtCore.pyqtSlot()
    def run_auto_lock(self, cal_data={'max':0.4,'min':0}):
        for i in range(240):
            self.give_bias.emit(i*0.004)
            time.sleep(0.01)
            self.wait_GUI()
            self.ask_DC.emit()
            self.wait_GUI()
            if self.DC > cal_data['max']:
                break
            else:
                continue
        pid_list=[0.1, 1, 0]
        self.start_pid.emit(pid_list)

    def wait_GUI(self):
        while self.wait_flag:
            APP.processEvents()
            time.sleep(0.01)
        self.wait_flag=True



    def change_wait_flag(self):
        self.wait_flag=False


    def renew_DC(self, DC=0):
        self.DC=DC
        self.logger.warning('get dc value')
        self.change_wait_flag()