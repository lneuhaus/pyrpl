from .SHG_lock import *
import numpy as np
import time
class SHGAutolock(SHGLock):
    def __init__(self):
        super(SHGAutolock,self).__init__(config='SHG_default')
        self.cal_data={'max': 0.4, 'min':np.mean(min_data)}
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
    @property
    def autoPDHlock(self):
        self.bias.offset=0
        self.scan_off
        for i in range(480):
            self.bias.offset=i*0.002
            self.rp.scope.setup(duration=0.1, trigger_source='immediately', input1='adc1', input2='dac1')
            DC = self.rp.scope.curve(1).mean()
            if DC > self.cal_data['max']:
                break
            else:
                continue
        self.pid_on
        return self.bias.offset
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