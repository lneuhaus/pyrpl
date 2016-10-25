# Code in this file make a RedPitaya device into 2 channel interferometer lock, which can lock to arbitrary phase.
import os
import numpy as np
from ..gui import RedPitayaGui
from ..memory import MemoryTree
#####
class InterferometerLock():
    def __init__(self, config='default'):
        _configdir = os.path.join(os.path.dirname(__file__), "i_config")
        self._configfile = os.path.join(_configdir, config + '.yml')
        self.c = MemoryTree(self._configfile)
        self.rp = RedPitayaGui(**self.c.redpitaya._dict, console_ns={'l':self})
        self.connect_rp()
        self.rp.gui()
    #
    def connect_rp(self):
        _config_asg = self.c.rp_mod_connection.asg
        _config_pid = self.c.rp_mod_connection.pid
        _config_iq = self.c.rp_mod_connection.iq
        self.connect_asg(**_config_asg._dict)
        self.connect_pid(**_config_pid._dict)
        self.connect_iq(**_config_iq._dict)
    #
    def connect_asg(self, waveform, frequency, amplitude, offset, output_direct):
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
    def connect_pid(self, input, output_direct):
        self.rp.pid0.input = input['pid0']
        self.rp.pid1.input = input['pid1']
        self.rp.pid2.input = input['pid2']
        self.rp.pid3.input = input['pid3']
        self.rp.pid0.output_direct = output_direct['pid0']
        self.rp.pid1.output_direct = output_direct['pid1']
        self.rp.pid2.output_direct = output_direct['pid2']
        self.rp.pid3.output_direct = output_direct['pid3']

    #
    def connect_iq(self, input, output_direct, output_signal):
        self.rp.iq0.input = input['iq0']
        self.rp.iq1.input = input['iq1']
        self.rp.iq0.output_direct=output_direct['iq0']
        self.rp.iq1.output_direct = output_direct['iq1']
        self.rp.iq0.output_signal = output_signal['iq0']
        self.rp.iq1.output_signal = output_signal['iq1']
    #
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
