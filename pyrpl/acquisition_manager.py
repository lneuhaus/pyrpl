from .attributes import StringProperty, LongProperty,\
     BoolProperty, SubModuleProperty
from .modules import BaseModule, SignalLauncher

from PyQt4 import QtCore, QtGui


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
            obj._start_acquisition()
        if val == "running_continuous":  # start acquisition. restart
            # averaging only if previous state was 'stop'
            if previous_state == 'stopped':
                obj._restart_averaging()
            obj._start_acquisition()
        if val in ["paused", "stopped"]:
            obj._stop_acquisition()

        if val in ["running_single", "running_continuous"]:
            obj._emit_signal_by_name('autoscale')
        return val

class SignalLauncherAM(SignalLauncher):
    """
    A signal launcher for the AcquisitionManager
    """
    display_curves = QtCore.pyqtSignal(list) # This signal is emitted when
    # curves need to be displayed the argument is [array(times),
    # array(curve1), array(curve2)] or [times, None, array(curve2)]
    autoscale = QtCore.pyqtSignal()


class AcquisitionManager(BaseModule):
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

    _signal_launcher = SignalLauncherAM
    _setup_attributes = ['running_state']
    _callback_attributes = []
    _section_name = None # don't make a section, don't make states

    data_current = None # placeholder for current curve
    data_avg = None # placeholder fo raveraged curve

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
                           "performed.",)
                       #default=1)


    def _init_module(self):
        self._module = self.parent
        self._timer = QtCore.QTimer()
        self._timer.setInterval(10)  # max. frame rate: 100 Hz
        self._timer.setSingleShot(True)
        self._running_state = "stopped"
        self.current_avg = 0
        self.avg = 1 # general remark: should be possible to specify that
                     # LongProperty.__init__
        self.data_current = None
        self.data_avg = None

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

    @property
    def curve_name(self):
        """
        name of the curve to create upon saving
        """
        return self._module.run_curve_name

    @curve_name.setter
    def curve_name(self, val):
        self._module.run_curve_name = val
        return val

    def single(self):
        """
        Performs an asynchronous acquisition of avg curves.
        The function returns a promise of the result:
        an object with a get() function that blocks until
        data is ready.
        """
        self.stop()
        self._module.setup()
        self._timer.start()

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
        d = self._module.get_setup_attributes()
        curves = [None, None]
        for ch, active in [(1, self._module.ch1_active),
                           (2, self._module.ch2_active)]:
            if active:
                d.update({'ch': ch,
                          'name': self.curve_name + ' ch' + str(ch)})
                curves[ch - 1] = self._save_curve(self.times,
                                                  self.data_avg[ch],
                                                  **d)
        return curves

    def _kill_timers(self):
        super(AcquisitionManager, self)._kill_timers()
        self._timer.stop()


class AcquisitionModule(BaseModule):
    _acquisition_manager_class = AcquisitionManager
    run = SubModuleProperty(_acquisition_manager_class)
    # to overwrite with appropriate Manager in derived class