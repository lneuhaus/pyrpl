from . import DspModule
from ..widgets.module_widgets import PwmWidget


class Pwm(DspModule):
    """Auxiliary outputs. PWM0-3 correspond to pins 17-20 on E2 connector.

    See  http://wiki.redpitaya.com/index.php?title=Extension_connectors
    to find out where to connect your output device to the board.
    Outputs are 0-1.8V, but we will map this to -1 to 1 V internally to
    guarantee compatibility with other modules. So setting a pwm voltage
    to '-1V' means you'll measure 0V, setting it to '+1V' you'll find 1.8V.

    Usage:
    pwm0 = AuxOutput(output='pwm0')
    pwm0.input = 'pid0'
    Pid(client, module='pid0').ival = 0 # -> outputs 0.9V on PWM0

    Make sure you have an analog low-pass with cutoff of at most 1 kHz
    behind the output pin, and possibly an output buffer for proper
    performance. Only recommended for temperature control or other
    slow actuators. Big noise peaks are expected around 480 kHz.

    Currently, only pwm1 and pwm2 are available.
    """

    _widget_class = PwmWidget
    _setup_attributes = ["input"]

    _gui_attributes = _setup_attributes

    def __init__(self, rp, name=None):
        super(Pwm, self).__init__(rp, name=dict(pwm0='in1',
                                                pwm1='in2')[name])
        # because pwm's input is using adc-input's plug
        self.name = name
        with self.do_setup:
            self.input ='off'
    """
    def __init__(self, client, name, parent): # name is 'pwm0' or 'pwm1'
        pwm_to_module = dict(pwm1='adc1', pwm2='adc2')
        # future options: , pwm2 = 'dac1', pwm3='dac2')
        super(AuxOutput, self).__init__(client,
                                        name=pwm_to_module[name],
                                        parent=parent)
    """

    output_direct = None
    output_directs = None
    _output_directs = None