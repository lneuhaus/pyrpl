from .module_attributes import *

from PyQt4 import QtCore, QtGui
from .async_utils import PyrplFuture


class AcquisitionError(ValueError): pass

class RunningStateProperty(StringProperty):
    """
    The state can be either:
      - running_single: taking a single acquisition (avg averages).
      averaging is automatically restarted.
      - running_continuous: taking a continuous acquisition
      - paused: acquisition interrupted, but no need to restart averaging
      at next call of running_continous
      - stopped: acquisition interrupted, averaging will restart at next
      call of running_continuous.
    """

    def set_value(self, obj, val):
        """
        This is the master property: changing this value triggers all the logic
        to change the acquisition mode
        """
        # touching the running_state cancels the pending future object
        obj._future.cancel()

        allowed = ["running_single",
                   "running_continuous",
                   "paused",
                   "stopped"]
        if not val in allowed:
            raise ValueError("Allowed states are : " + ', '.join(allowed))
        previous_state = obj.running_state

        super(RunningStateProperty, self).set_value(obj, val)

        if val == "running_single":
            # restart averaging and launch avg acquisitions
            obj._restart_averaging()
            obj._restart_averaging_called = True
            obj._start_acquisition()
        if val == "running_continuous":  # start acquisition. restart
            # averaging only if previous state was 'stop'
            if previous_state == 'stopped' or not \
                    obj._restart_averaging_called:
                obj._restart_averaging()
                obj._restart_averaging_called = True
            obj._start_acquisition()
        if val in ["paused", "stopped"]:
            obj._stop_acquisition()
        if val in ["running_single", "running_continuous"]:
            obj._emit_signal_by_name('autoscale')
        return val


class SignalLauncherAcquisitionManager(SignalLauncher):
    """
    A signal launcher for the AcquisitionManager
    """
    display_curve = QtCore.pyqtSignal(list) # This signal is emitted when
    # curves need to be displayed the argument is [array(times),
    # array(curve1), array(curve2)] or [times, None, array(curve2)]
    autoscale = QtCore.pyqtSignal()

    # For now, the following signals are only implemented with NA.
    update_point = QtCore.pyqtSignal(int) # used in NA only
    scan_finished = QtCore.pyqtSignal() # used in NA only
    clear_curve = QtCore.pyqtSignal()   # NA only


class SignalLauncherAcquisitionModule(SignalLauncher):
    """ class that takes care of emitting signals to update all possible
    displays """

    def connect_widget(self, widget):
        """
        In addition to connecting the module to the widget, also connect the
        acquisition manager. (At some point, we should make a separation
        between module widget and acquisition manager widget).
        """
        super(SignalLauncherAcquisitionModule, self).connect_widget(widget)
        self.module.run._signal_launcher.connect_widget(widget)


class AcquisitionManager(Module):
    """
    The asynchronous mode is supported by a sub-object "run"
    of the module. When an asynchronous acquisition is running
    and the widget is visible, the current averaged data are
    automatically displayed. Also, the run object provides a
    function save_curve to store the current averaged curve
    on the hard-drive.

    The full API of the "run" object is the following.

    public methods (All methods return immediately)
    -----------------------------------------------
     - single(): performs an asynchronous acquisition of avg curves.
     The function returns a promise of the result:
     an object with a ready() function, and a get() function that
     blocks until data is ready.
     - continuous(): continuously acquires curves, and performs a
     moving average over the avg last ones.
     - pause(): stops the current acquisition without restarting the
     averaging
     - stop(): stops the current acquisition and restarts the averaging.
     - save_curve(): saves the currently averaged curve (or curves for scope)
     - curve(): the currently averaged curve

    Public attributes:
    ------------------
     - running_state: either 'running_continuous', 'running_single',
     'paused', 'stopped'. Changing the flag actually performs the necessary
     actions
     - curve_name: name of the curve to create upon saving
     - avg: number of averages in single (not to confuse with averaging per
     point)
     - data_last: array containing the last curve acquired
     - data_averaged: array containing the current averaged curve
     - current_average: current number of averages
    """

    _signal_launcher = SignalLauncherAcquisitionManager
    _setup_attributes = ['running_state', 'avg', 'curve_name']
    _callback_attributes = []
    #_section_name = None # don't make a section, don't make states

    #The format for curves are:
    #   scope: np.array(times, ch1, ch2)
    #   specan or na: np.array(frequencies, data)
    data_x = None # placeholder for current x-data
    data_current = None # placeholder for current curve
    data_avg = None # placeholder for averaged curve

    running_state = RunningStateProperty(doc="""
    The state can be either:
      - running_single: taking a single acquisition (avg averages).
      averaging is automatically restarted.
      - running_continuous: taking a continuous acquisition
      - paused: acquisition interrupted, but no need to restart averaging
      at next call of running_continous
      - stopped: acquisition interrupted, averaging will restart at next
      call of running_continuous.
    """)
    avg = LongProperty(doc="number of curves to average in single mode. In "
                           "continuous mode, a moving window average is "
                           "performed.",
                       default=1)
    curve_name = StringProperty(doc="name of the curve to save.")

    def _init_module(self):
        super(AcquisitionManager, self)._init_module()
        self._module = self.parent
        self._timer = QtCore.QTimer()
        self._timer.setInterval(10)  # max. frame rate: 100 Hz
        self._timer.setSingleShot(True)
        self._running_state = "stopped"
        self.current_avg = 0
        self.curve_name = self.name + " curve"
        self.data_x = None
        self.data_current = None
        self.data_avg = None
        self._restart_averaging_called = False # _restart_averaging needs to
        self._future = PyrplFuture()
        # be called at least once (even if module is loaded in paused for
        # instance).

    def _restart_averaging(self):
        """
        Resets the data containers self._data_current and _data_avg for the
        coming run.
        :return:
        """
        raise NotImplementedError()

    def _start_acquisition(self):
        """
        Start an asynchronous acquisition without taking care of averaging
        :return:
        """
        self._module.setup()
        self._timer.start()

    def _stop_acquisition(self):
        """
        Stops an asynchronous acquisition without taking care of averaging
        :return:
        """
        self._timer.stop()

    def _emit_signal_by_name(self, signal_name, *args, **kwds):
        """Let's the module's signal_launcher emit signal name"""
        self._signal_launcher.emit_signal_by_name(signal_name, *args, **kwds)

    def single(self):
        """
        Performs an asynchronous acquisition of avg curves.
        The function returns a promise of the result:
        an object with a result() function that blocks until
        data is ready.

        If the instrument is already in state 'run_single', then, raises
        AcquisitionError.

        If the running_state of the instrument is modified before the end
        of the scan, the future object will be cancelled.
        """
        if self.running_state == 'running_single':
            raise AcquisitionError("Instrument %s is already in mode "
                                   "'run_single'"%self._module.name)
        self.running_state = 'running_single'
        self._future = PyrplFuture()
        return self._future

    def continuous(self):
        """
        continuously acquires curves, and performs a moving
        average over the avg last ones.
        """
        self.running_state = 'running_continuous'

    def pause(self):
        """
        Stops the current acquisition without restarting the averaging
        """
        self.running_state = 'paused'

    def stop(self):
        """
        Stops the current acquisition and averaging will be restarted
        at next run.
        """
        self.running_state = 'stopped'

    def save_curve(self):
        """
        Saves the curve(s) that is (are) currently displayed in the gui in
        the db_system. Also, returns the list [curve_ch1, curve_ch2]...
        """
        params = self._module.setup_attributes
        params.update(name=self.curve_name)
        curve = self._save_curve(self.data_x,
                                 self.data_avg,
                                 **params)
        return curve

    def _kill_timers(self):
        super(AcquisitionManager, self)._kill_timers()
        self._timer.stop()

    def _set_result_in_future(self):
        """
        Updates the value of self._future with the tuple: (data_x, data_avg).
        In practice, this function is called at the end of a single scan.
        """
        self._future.set_result((self.data_x, self.data_avg))


class AcquisitionModule(Module):
    # run = ModuleProperty(AcquisitionManager)
    # to overwrite with appropriate Manager in derived class
    _signal_launcher = SignalLauncherAcquisitionModule

    def _callback(self):
        """
        Whenever a setup_attribute is touched, stop the acquisition
        immediately (this behavior is not visible in scope because nothing
        is listed in _callback_attributes).
        """
        if self.run.running_state in ['running_single',
                                      'running_continuous',
                                      'paused']:
            self.run.stop()
