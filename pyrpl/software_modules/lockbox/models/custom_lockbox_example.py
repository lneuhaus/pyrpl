# these imports are the standard imports for required for derived lockboxes
from pyrpl.software_modules.lockbox import *
from pyrpl.software_modules.loop import *

# Any InputSignal must define a class that contains the function "expected_signal(variable)" that returns the expected
# signal value as a function of the variable value. This function ensures that the correct setpoint and a reasonable
# gain is chosen (from the derivative of expected_signal) when this signal is used for feedback.
class CustomInputClass(InputSignal):
    """ A custom input signal for our customized lockbox. Please refer to the documentation on the default API of
    InputSignals"""
    def expected_signal(self, variable):
        # For example, assume that our analog signal is proportional to the square of the variable
        return self.calibration_data.min + self.custom_gain_attribute * self.lockbox.custom_attribute * variable**2

    # If possible, you should explicitely define the derivative of expected_signal(variable). Otherwise, the derivative
    # is estimated numerically which might lead to inaccuracies and excess delay.
    def expected_slope(self, variable):
        return 2.0 * self.custom_gain_attribute * self.lockbox.custom_attribute * variable

    # Signals can have their specific attributes, including gui support.
    # Please refer to the Lockbox example for more explanations on this.
    _setup_attributes = ["custom_gain_attribute"]
    _gui_attributes = ["custom_gain_attribute"]
    custom_gain_attribute = FloatProperty(default=1.0,
                                          min=-1e10,
                                          max=1e10,
                                          increment=0.01,
                                          doc="custom factor for each input signal")

    # A customized calibration method can be used to implement custom calibrations. The calibration method of the
    # InputSignal class retrieves min, max, mean, rms of the input signal during a sweep and saves them as class
    # attributes, such that they can be used by expected_signal().
    def calibrate(self):
        """ This is a simplified calibration method. InputSignal.calibrate works better than this in most cases. """
        self.lockbox.sweep()
        # get a curve of the signal during the sweep
        curve,_ = self.sweep_acquire()
        # fill self.mean, min, max, rms with values from acquired curve.
        self.calibration_data.get_stats_from_curve(curve=curve)


class CustomLockbox(Lockbox):
    """ A custom lockbox class that can be used to implement customized feedback controllers"""

    # this syntax for the definition of inputs and outputs allows to conveniently access inputs in the API
    inputs = LockboxModuleDictProperty(custom_input_name1=CustomInputClass,
                                       custom_input_name2=CustomInputClass)

    outputs = LockboxModuleDictProperty(slow_output=OutputSignal,
                                             fast_output=OutputSignal,
                                             pwm_output=OutputSignal)

    # the name of the variable to be stabilized to a setpoint. inputs.expected_signal(variable) returns the expected
    # signal as a function of this variable
    variable = 'displacement'

    # attributes are defined by descriptors
    custom_attribute = FloatProperty(default=1.0, increment=0.01, min=1e-5, max=1e5)

    # list of attributes that are mandatory to define lockbox state. setup_attributes of all base classes and of all
    # submodules are automatically added to the list by the metaclass of Module
    _setup_attributes = ["custom_attribute"]
    # attributes that are displayed in the gui. _gui_attributes from base classes are also added.
    _gui_attributes = ["custom_attribute"]

    # if nonstandard units are to be used to specify the gain of the outputs, their conversion to Volts must be defined
    # by a property called _unitname_per_V
    _mV_per_V = 1000.0
    _units = ["V", "mV"]

    # overwrite any lockbox functions here or add new ones
    def custom_function(self):
        self.calibrate_all()
        self.unlock()
        self.lock()

# in loop.py:
#class ExampleLoop(LockboxPlotLoop):
#    def loop(self):
#        self.plot.append(green=np.sin(time()), red=np.cos(time()))

class ExampleLoop(LockboxPlotLoop): # or inherit from
    def __init__(self, parent, name=None):
        super(ExampleLoop, self).__init__(parent, name=name)
        self.c.n = 0
        self.last_texcess = 0
        self.result_ready = "not ready"

    def loop(self):
        # attention: self.time() is FPGA time, time() is plot-relevant time
        self.c.n += 1
        tact = time() - self.plot.plot_start_time
        tmin = self.interval * self.c.n
        texcess = tact - tmin
        dt = texcess - self.last_texcess
        self.last_texcess = texcess
        self.plot.append(green=np.sin(2.0*np.pi*tact*3), #/self.lockbox.interval),
                         red=dt)
        if self.c.n == 100:
            self.result = 42
            self.result_ready = True
            self._clear()


class ExampleLoopLockbox(Lockbox):
    loop = None
    _gui_attributes = ["start", "stop", "interval"]

    interval = FloatProperty(default=0.01, min=0)

    def start(self):
        self.stop()
        self.loop = ExampleLoop(parent=self,
                                name="example_loop",
                                interval=self.interval)

    def stop(self):
        if self.loop is not None:
            self.loop._clear()
            self.loop = None


class GalvanicIsolationLoopLockbox(Lockbox):
    """ an example for a loop fully described in the lockbox class definition"""
    _gui_attributes = ["start_gi", "stop_gi", "gi_interval"]
    gi_interval = FloatProperty(default=0.05, min=0, max=1e10,
                                doc="Minimum interval at which the loop updates the second redpitaya output")

    def start_gi(self):
        self.stop_gi()
        # start second redpitaya
        if not hasattr(self, 'second_pyrpl') or self.second_pyrpl is None:
            from pyrpl import Pyrpl
            self.second_pyrpl = Pyrpl("second_redpitaya", hostname="_FAKE_REDPITAYA_")
        # start loop
        self.galvanic_isolation_loop = LockboxLoop(parent=self,
            name="galvanic_isolation_loop",
            interval=self.gi_interval,
            loop_function=self.galvanic_isolation_loop_function)

    def galvanic_isolation_loop_function(self):
        """ the loop function to be executed"""
        # read an output value from this lockbox and set it as the output of the second redpitaya
        self.second_pyrpl.rp.asg0.offset = self.pyrpl.rp.sampler.pid0
        # only for debugging:
        # self.second_pyrpl.rp.asg0.offset = np.sin(2 * np.pi * time() - self.galvanic_isolation_loop.loop_start_time)

    def stop_gi(self):
        if hasattr(self, 'galvanic_isolation_loop') and self.galvanic_isolation_loop is not None:
            self.galvanic_isolation_loop._clear()
        self.galvanic_isolation_loop = None


class ShortLoopLockbox(Lockbox):
    """ an example for very short loop description"""

    def plot_sin_and_in1(lockbox_self, loop_self):
        """ if you pass an instance_method of the lockbox, it should take two arguments:
        the instance of the lockbox (self) and the instance of the loop"""
        loop_self.plot.append(green=np.sin(2*np.pi*loop_self.time),
                              red=lockbox_self.pyrpl.rp.sampler.in1)
        if loop_self.n > 100:  # auto-stop after 1000 cycles
            loop_self._clear()

    loop = ModuleProperty(LockboxPlotLoop,
                          interval=0.05,
                          autostart=True,
                          loop_function=plot_sin_and_in1)
