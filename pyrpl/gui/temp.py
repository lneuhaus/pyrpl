from pyrpl import RedPitaya


from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import pyqtgraph as pg

win = pg.GraphicsWindow(title="Basic plotting examples")

p6 = win.addPlot(title="Updating plot")
curve = p6.plot(pen='y')


import time

FREQUENCY = 20

REDPITAYA = None

def get_redpitaya():
    return RedPitaya(hostname="10.214.1.28")


def setup_all():
    setup()
    setup_asg()
    timer.start()

def setup():
    global REDPITAYA
    if REDPITAYA is None:
        REDPITAYA = RedPitaya(hostname="10.214.1.28")
    REDPITAYA.scope.trigger_source = 'asg_positive_edge'
    REDPITAYA.scope.threshold_ch1 = 0.5
    REDPITAYA.scope.input1= "adc2"#"asg1"
    REDPITAYA.scope.input2 = 'pid0'
    
    
def setup_asg():
    asg = REDPITAYA.asg1 
    asg.output_direct = 'out2'
    asg.setup(waveform="ramp",
              frequency=FREQUENCY,
              amplitude=1,
              offset=0,
              trigger_source='immediately')


def launch_scope():
    global REDPITAYA
    if REDPITAYA is None:
        REDPITAYA = RedPitaya(hostname="10.214.1.28")

    """
    print "armed:", REDPITAYA.scope.trigger_armed
    print "source:", REDPITAYA.scope.trigger_source
    """
    
    


    s = REDPITAYA.scope
    if s.trigger_armed:
        timer.start()
        return
    curve.setData(s.data_ch1)
    

    # turn off the trigger while we configure
    s.trigger_armed = False

    # reset everything
    s.reset_writestate_machine=True

    # trig at zero volt crossing
    s.threshold_ch1 = 0.5
    # positive/negative slope is detected by waiting for input to 
    # sweept through hysteresis around the trigger threshold in 
    # the right direction 
    s.hysteresis_ch1 = 0.01

    # trigger on the input signal positive slope
    s.trigger_source = 'asg_negative_edge'

    # take data symetrically around the trigger event
    s.trigger_delay=s.data_length//2 

    # set decimation factor to 8 -> full scope trace is 8ns * 2^14 * decimation = 1ms long
    s.decimation = 1024

    # arm the trigger - start filling the buffer
    s.trigger_armed = True

    if s.trigger_source == 'immediately':
        s.sw_trig() 

    
    

    REDPITAYA.asg1.setup(waveform="ramp",
              frequency=FREQUENCY,
              amplitude=1,
              offset=0.5,
              trigger_source='off')
    REDPITAYA.asg1.trig()

    timer.start()

    
    
     
    


setup_timer = QtCore.QTimer()
setup_timer.setSingleShot(True)
setup_timer.setInterval(10)
setup_timer.timeout.connect(setup_all)

timer = QtCore.QTimer()
timer.setSingleShot(True)
timer.setInterval(1)
timer.timeout.connect(launch_scope)

setup_timer.start()
