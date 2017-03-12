"""
Everything that involves asynchronicity in acquisition instruments such as
getting curves, ot continuously averaging curves is confined in this file.

Using the coroutine syntax introduced in python 3.4+ would make the code
more elegant, but it would not be compatible with python 2.7. Hence we have
chosen to implement all asynchronous methods such that a promise is returned (a
Future-object in python). The promise implements the following methods:
   - await_result(): returns the acquisition result once it is ready.
   - add_done_callback(func): the function func(value) is used as
   "done-callback)

All asynchronous methods also have a blocking equivalent that directly
returns the result once it is ready:
     curve_async  <---> curve
     single_async <---> single

Finally, this implmentation using standard python Futures makes it
possible to use transparently pyrpl asynchronous methods inside python 3.x
coroutines.
example:
--------

from asyncio import ensure_future, event_loop

async def my_acquisition_routine(n):
    for i in range(n):
        print("acquiring scope")
        fut = ensure_future(p.rp.scope.run_single())
        print("acquiring na")
        data2 = await p.networkanalyzer.run_single()
        # both acquisitions are carried out simultaneously
        data1 = await fut
        print("loop %i"%i, data1, data2)

ensure_future(my_acquisition_coroutine(10))
eventloop.run_until_complete()
"""


from .module_attributes import *

from PyQt4 import QtCore, QtGui
from .async_utils import PyrplFuture, Future, MainThreadTimer, CancelledError


class AcquisitionError(ValueError): pass


class CurveFuture(PyrplFuture):
    """
    The basic acquisition of instruments is an asynchronous process:

    For instance, when the scope acquisition has been launched, we know
    that the curve won't be ready before duration(), but if the scope is
    waiting for a trigger event, this could take much longer. Of course,
    we want the event loop to stay alive while waiting for a pending curve.
    That's the purpose of this future object.

    After its creation, it will perform the following actions:
     1. stay inactive for a time given by instrument._remaining_time()
     2. after that, it will check every min_refresh_delay if a new curve is
     ready with instrument._data_ready()
     3. when data is ready, its result will be set with the instrument data,
     as returned by instrument._get_data()
    """

    def __init__(self, acquisition_manager, min_delay_ms=20):
        self._run = acquisition_manager
        self._instrument = acquisition_manager._module
        self.min_delay_ms = min_delay_ms
        super(CurveFuture, self).__init__()
        self._init_timer()

    def start(self):
        self._instrument._start_acquisition()
        super(CurveFuture, self).start()

    def _init_timer(self):
        if self.min_delay_ms == 0:
            # make sure 1st instrument interrogation occurs before time
            delay = self._instrument._remaining_time() * 1000 - 1
        else:
            # 1 ms loss due to timer inaccuracy is acceptable
            delay = max(self.min_delay_ms,
                        self._instrument._remaining_time() * 1000)

        self._timer = MainThreadTimer(delay)
        self._timer.timeout.connect(self._set_data_as_result)
        self._timer.start()

    def _get_one_curve(self):
        if self._instrument._data_ready():
            return self._instrument._get_curve()
        else:
            return None

    def _set_data_as_result(self):
        data = self._get_one_curve()
        if data is not None:
            self.set_result(data)
        else:
            self._timer.setInterval(self.min_delay_ms)
            self._timer.start()

    def cancel(self):
        self._timer.stop()
        super(CurveFuture, self).cancel()


class RunFuture(PyrplFuture):
    """
    Uses several CurveFuture to perform an average.

    2 extra functions are provided to control the acquisition:

    pause(): stalls the acquisition

    start(): (re-)starts the acquisition (needs to be called at the beginning)
    """
    _launch_at_startup = True

    def __init__(self, acquisition_manager, continuous_run):
        self._continuous_run = continuous_run
        self._run = acquisition_manager
        self._instrument = acquisition_manager._module
        super(RunFuture, self).__init__()
        self.current_avg = 0
        self.data_x = self._instrument._data_x()
        self.data_avg = None
        self._fut = None

    def _new_curve_arrived(self, curve):
        try:
            result = curve.result()
        except CancelledError:
            self.cancel()
            return

        self.current_avg = min(self.current_avg + 1, self._run.avg)

        if self.data_avg is None:
            self.data_avg = result
        else:
            self.data_avg = (self.data_avg * (self.current_avg - 1) +
                             result)/self.current_avg

        self._run._emit_signal_by_name('display_curve',
                                       [self.data_x,
                                        self.data_avg])

        if self._is_run_over():
            self.set_result(self.data_avg)
            self._run.running_state = "stopped"
        else:
            self._fut = self._run._curve_async(self._get_delay())
            self._fut.add_done_callback(self._new_curve_arrived)

    def _get_delay(self):
        if self._continuous_run:
            return self._run.MIN_DELAY_CONTINUOUS_MS
        else:
            return self._run.MIN_DELAY_SINGLE_MS

    def _is_run_over(self):
        if self._continuous_run:
            return False
        else:
            return self.current_avg >= self._run.avg

    def cancel(self):
        if self._fut is not None:
            self._fut.cancel()
        super(RunFuture, self).cancel()

    def pause(self):
        if self._fut is not None:
            self._fut.cancel()

    def start(self):
        self._fut = self._run._curve_async(self._get_delay())
        self._fut.add_done_callback(self._new_curve_arrived)


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
        # touching the running_state cancels the pending future objects
        # (no effect if future is already done)
        obj._curve_future.cancel()

        allowed = ["running_single",
                   "running_continuous",
                   "paused",
                   "stopped"]
        if not val in allowed:
            raise ValueError("Allowed states are : " + ', '.join(allowed))
        previous_state = obj.running_state

        super(RunningStateProperty, self).set_value(obj, val)

        if val == "running_single":
            # acquire as fast as possible avg curves
            obj._run_future = obj._get_new_single_future()
            obj._run_future.start()
        if val == "running_continuous":
            obj._module._start_acquisition()
            if previous_state == 'stopped': # restart averaging...
                obj._run_future.cancel()
                obj._run_future = obj._get_new_continuous_future()
            obj._run_future.start()
        if val in ["paused", "stopped"]:
            obj._run_future.pause()
        if val in ["running_single", "running_continuous"]:
            obj._emit_signal_by_name('autoscale')


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
     - current_avg: current number of averages
    """

    _signal_launcher = SignalLauncherAcquisitionManager
    _setup_attributes = ['running_state', 'avg', 'curve_name']
    _callback_attributes = []
    #_section_name = None # don't make a section, don't make states
    MIN_DELAY_SINGLE_MS = 0 # async acquisition should be as fast as
    # possible
    MIN_DELAY_CONTINUOUS_MS = 40 # leave time for the event loop in
    # continuous

    #The format for curves are:
    #   scope: np.array(times, ch1, ch2)
    #   specan or na: np.array(frequencies, data)
    # data_x = None # placeholder for current x-data
    # data_current = None # placeholder for current curve
    # data_avg = None # placeholder for averaged curve

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
        # self._timer = QtCore.QTimer()
        # self._timer.setInterval(10)  # max. frame rate: 100 Hz
        # self._timer.setSingleShot(True)
        self._running_state = "stopped"
        self.curve_name = self.name + " curve"
        # self.data_x = None
        # self.data_current = None
        # self.data_avg = None
        # self._restart_averaging_called = False # _restart_averaging needs to

        # The 2 first promises are not initialized with CurveFuture and
        # SingleFuture because we don't want them to run at the beginning.
        self._curve_future = Future()
        self._run_future = RunFuture(self, continuous_run=True)

    def _get_new_curve_future(self, min_delay_ms):
        return CurveFuture(self, min_delay_ms=min_delay_ms)

    def _get_new_single_future(self):
        return RunFuture(self, continuous_run=False)

    def _get_new_continuous_future(self):
        return RunFuture(self, continuous_run=True)

    def _emit_signal_by_name(self, signal_name, *args, **kwds):
        """Let's the module's signal_launcher emit signal name"""
        self._signal_launcher.emit_signal_by_name(signal_name, *args, **kwds)

    def _curve_async(self, min_delay_ms):
        """
        Same as curve_async except this function can be used in any
        running_state.
        """
        self._curve_future.cancel()
        self._module._start_acquisition()
        self._curve_future = self._get_new_curve_future(
                                    min_delay_ms=min_delay_ms)
        return self._curve_future

    def curve_async(self):
        """
        - Launches the acquisition for one curve with the current parameters.
        - If running_state is not "stopped", stops the current acquisition.
        - If rolling_mode is True, raises an exception.
        - Immediately returns a future object representing the curve.
        - The curve can be retrieved by calling result(timeout) on the
        future object.
        - The future is cancelled if the instrument's state is changed
        before the end of the acquisition, or another call to curve_async()
        or curve() is made on the same instrument.
        """
        if self.running_state is not "Stopped":
            self.stop()
        return self._curve_async(0)

    def curve(self, timeout=None):
        """
        Same as curve_async, except:
        1. the function will not return until the curve is ready or tumeout
        occurs.
        2. the function directly returns an array with the curve instead of
        a future object
        """
        return self.curve_async().result(timeout)

    def single_async(self):
        """
        - Performs an asynchronous acquisition of avg curves.
        - If running_state is not stop, stops the current acquisition.
        - Immediately returns a future object representing the curve.
        - The curve can be retrieved by calling result(timeout) on the
        future object.
        - The future is cancelled if the instrument's state is changed
        before the end of the acquisition.
        """
        self.running_state = 'running_single'
        return self._run_future

    def single(self, timeout=None):
        """
        Same as single_async, except:
        1. the function will not return until the averaged curve is ready or
        timeout occurs.
        2. the function directly returns an array with the curve instead of
        a future object.
        """
        return self.single_async().await_result(timeout)

    def continuous(self):
        """
        continuously acquires curves, and performs a moving
        average over the avg last ones.
        """
        self.running_state = 'running_continuous'
        # return self._continuous_future

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
        self._curve_future.cancel()
        self._single_future.cancel()
        self._continuous_future.cancel()

    @property
    def current_avg(self):
        return self._run_future.current_avg


class AcquisitionModule(Module):
    # run = ModuleProperty(AcquisitionManager)
    # to overwrite with appropriate Manager in derived class
    _signal_launcher = SignalLauncherAcquisitionModule

    def _remaining_time(self):
        """
        remaining time (in seconds) until the data has a chance to be ready.
        In the case of scope, where trigger might delay the acquisition,
        this is the minimum time to wait in the "best case scenario" where
        the acquisition would have started immediately after setup().
        """
        raise NotImplementedError("To implement in derived class")

    def _data_ready(self):
        """
        :return: True or False
        """
        raise NotImplementedError('To implement in derived class')

    def _get_curve(self):
        """
        get the curve from the instrument.
          a 1D array for single channel instruments
          a 2*n array for the scope
        """
        raise NotImplementedError

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

    def curve(self, timeout=None):
        """
        :returns the curve acquired (or currently acquiring) due to the
        last call of setup().

        Raises an exception if setup was never called before

        Repeated calls (without setup() in between) will return the same data.

        This function is identical to self.run.curve(), except that:
          1. it will not return until the data are ready or timeout occurred.
          2. it directly returns the curve data (instead of a future).
          3. No gui display occurs whil calling this curve.

        You should avoid calling this function when scope is running single
        or continuous.
        """
        data = self.run.curve()
        return data.result(timeout)

    def single(self, timeout=None):
        """
        Returns an average of run.avg curves

        This function is identical to self.run.single(), except that:
        1. it will not return until the data are ready or timeout occurred.
        2. it directly returns the curve data (instead of a future).
        """
        data = self.run.single()
        return data.result(timeout)