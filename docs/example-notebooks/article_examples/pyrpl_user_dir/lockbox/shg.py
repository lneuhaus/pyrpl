# these imports are the standard imports for required for derived lockboxes
#from pyrpl.software_modules.lockbox import
#from .. import *
import logging
from pyrpl.software_modules.lockbox.models.fabryperot import FPPdh, FabryPerot, FPTransmission, FPReflection
from pyrpl.software_modules.lockbox.output import OutputSignal
from pyrpl.software_modules.lockbox.input import InputSignal
from pyrpl.software_modules.lockbox import LockboxModuleDictProperty, FloatProperty, PiezoOutput, Lockbox
from pyrpl.hardware_modules.asg import Asg0, Asg1
from pyrpl.hardware_modules.pid import Pid
from pyrpl.widgets.module_widgets import OutputSignalWidget
from pyrpl.software_modules.module_managers import InsufficientResourceError

# Any InputSignal must define a class that contains the function "expected_signal(variable)" that returns the expected
# signal value as a function of the variable value. This function ensures that the correct setpoint and a reasonable
# gain is chosen (from the derivative of expected_signal) when this signal is used for feedback.

class PDHtransmission(FPPdh):
    def is_locked(self, loglevel=logging.INFO):
        # simply perform the is_locked with the reflection error signal
        return self.lockbox.inputs.transmission_SHG.is_locked(loglevel=loglevel)

class FPPdh(FPPdh):
    def is_locked(self, loglevel=logging.INFO):
        # simply perform the is_locked with the reflection error signal
        return self.lockbox.inputs.reflection_MCIR.is_locked(loglevel=loglevel)

class InputSignal(InputSignal):

    def sweep_SHG_acquire(self):
        """
        returns an experimental curve in V obtained from a sweep of the
        lockbox.
        """
        try:
            with self.pyrpl.scopes.pop(self.name) as scope:
                self.lockbox.sweep_SHG()
                if "sweep" in scope.states:
                    scope.load_state("sweep")
                else:
                    scope.setup(input1=self.signal(),
                                input2=self.lockbox.outputspiezo_SHG.pid.output_direct,
                                trigger_source=self.lockbox.asg.name,
                                trigger_delay=0,
                                duration=1./self.lockbox.asg.frequency,
                                ch1_active=True,
                                ch2_active=True,
                                average=True,
                                trace_average=1,
                                running_state='stopped',
                                rolling_mode=False)
                    scope.save_state("autosweep")
                curve1, curve2 = scope.curve(timeout=1./self.lockbox.asg.frequency+scope.duration)
                times = scope.times
                curve1 -= self.calibration_data._analog_offset
                return curve1, times
        except InsufficientResourceError:
            # scope is blocked
            self._logger.warning("No free scopes left for sweep_acquire. ")
            return None, None

    def calibrate_SHG(self, autosave=False):
        """
        This function should be reimplemented to measure whatever property of
        the curve is needed by expected_signal.
        """
        curve, times = self.sweep_SHG_acquire()
        if curve is None:
            self._logger.warning('Aborting calibration because no scope is available...')
            return None
        self.calibration_data.get_stats_from_curve(curve)
        # log calibration values
        self._logger.info("%s calibration successful - Min: %.3f  Max: %.3f  Mean: %.3f  Rms: %.3f",
                          self.name,
                          self.calibration_data.min,
                          self.calibration_data.max,
                          self.calibration_data.mean,
                          self.calibration_data.rms)
        # update graph in lockbox
        self.lockbox._signal_launcher.input_calibrated.emit([self])
        # save data if desired
        if autosave:
            params = self.calibration_data.setup_attributes
            params['name'] = self.name+"_calibration"
            newcurve = self._save_curve(times, curve, **params)
            self.calibration_data.curve = newcurve
            return newcurve
        else:
            return None



class OutputSignal(OutputSignal):
    def sweep_SHG(self):
        self.pid.input = self.lockbox.asg_SHG
        self.lockbox.asg_SHG.setup(amplitude=self.sweep_amplitude,
                               offset=self.sweep_offset,
                               frequency=self.sweep_frequency,
                               waveform=self.sweep_waveform,
                               trigger_source='immediately',
                               cycles_per_burst=0)
        self.pid.setpoint = 0.
        self.pid.p = 1.
        self.current_state = 'sweep'




class SHG(FabryPerot):



    # this syntax for the definition of inputs and outputs allows to conveniently access inputs in the API
    inputs = LockboxModuleDictProperty(transmission_SHG=FPTransmission,
                                       PDH_SHG=PDHtransmission)

    outputs = LockboxModuleDictProperty(piezo_SHG=PiezoOutput)
                                         #    piezo_MCIR=PiezoOutput)





    # the name of the variable to be stabilized to a setpoint. inputs.expected_signal(variable) returns the expected
    # signal as a function of this variable
    variable = 'displacement'

    @property
    def free_spectral_range_SHG(self):
        """ returns the cavity free spectral range in Hz """
        return 2.998e8 / self.round_trip_length_SHG




    # if nonstandard units are to be used to specify the gain of the outputs, their conversion to Volts must be defined
    # by a property called _unitname_per_V
    _mV_per_V = 1000.0
    _units = ["V", "mV"]

    # overwrite any lockbox functions here or add new ones
    def custom_function(self):
        self.calibrate_all()
        self.unlock()
        self.lock()

    def synchronize_iqs(self):
        self.inputs.PDH_SHG.iq.synchronize_iqs()


    def sweep_SHG(self):
        """
        Performs a sweep of one of the output. No output default kwds to avoid
        problems when use as a slot.
        """
        self.outputs.piezo_SHG.sweep()
        self.current_state = "sweep"


    def asg_SHG(self):
        """ the asg being used for SHG sweeps """
        if not hasattr(self, '_asg') or self._asg is None:
            self._asg = self.pyrpl.asgs.pop(self.name)
        return self._asg



    def calibrate_SHG(self):
        self.inputs.transmission_SHG.calibrate_SHG()



