"""
Everything involving asynchronicity in acquisition instruments is in this file.

In particular, this includes getting curves and continuously averaging curves.

Using the coroutine syntax introduced in python 3.4+ would make the code
more elegant, but it would not be compatible with python 2.7. Hence we have
chosen to implement all asynchronous methods such that a promise is returned (a
Future-object in python). The promise implements the following methods:

- await_result(): returns the acquisition result once it is ready.
- add_done_callback(func): the function func(value) is used as "done-callback)

All asynchronous methods also have a blocking equivalent that directly
returns the result once it is ready:

- curve_async  <---> curve
- single_async <---> single

Finally, this implmentation using standard python Futures makes it
possible to use transparently pyrpl asynchronous methods inside python 3.x
coroutines.

Example:

    This example shows a typical acquisition use case where a sequence of
    n aquisitions of simultaneous oscilloscope and network analyzer traces
    are launched
    ::

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
from copy import copy
from .async_utils import ensure_future, sleep, wait, Event

from .module_attributes import *


class AcquisitionError(ValueError):
    pass


class RunningStateProperty(SelectProperty):
    def __init__(self, options=["running_single",
                                "running_continuous",
                                "paused_single",
                                "paused_continuous",
                                "stopped"], **kwargs):
        """
        A property to indicate whether the instrument is currently running or not.

        Changing the running_state performs the necessary actions to enable the
        selected state. The state can be one of the following:

        - 'running_single': takes a single acquisition (trace_average averages). Acquisitions are automatically restarted until the desired number of averages is acquired.
        - 'running_continuous': continuously takes a acquisitions, eternally averages and restarts automatically.
        - 'paused': acquisition interrupted, but no need to restart averaging at next call of running_continous.
        - 'stopped': acquisition interrupted, averaging will restart at next call of running_continuous.
        """
        super(RunningStateProperty, self).__init__(options=options, **kwargs)

    #  Changing running_state is handled here instead of inside _setup()
    # (with a call_setup=True option) because the precise actions to be
    # taken depend on the previous state of running_state. Such a behavior
    # would not be straightforward to implement in _setup()
    # def set_value(self, obj, val):
    #     """
    #     This is the master property: changing this value triggers all the logic
    #     to change the acquisition mode
    #     """
    #     # touching the running_state cancels the pending curve_future object
    #     # (no effect if future is already done)
    #     ###obj._curve_future.cancel()
    #     previous_state = obj.running_state
    #     SelectProperty.set_value(self, obj, val)
    #     if val == "running_single":
    #         # acquire as fast as possible trace_average curves
    #         obj.setup()
    #     elif val == "running_continuous":
    #         if previous_state == 'stopped':  #  restart averaging...
    #             obj.setup()
    #         else:
    #             obj._run_future._set_run_continuous() # if previous run was
    #             # "running_single" keep averaging in the same run, simply make
    #             # it continuous
    #             obj._run_future.start()
    #     elif val in ["paused", "stopped"]:
    #         if hasattr(obj, '_run_future'):
    #             obj._run_future.cancel() #  single cannot be resumed
    #             #  on the other hand, continuous can still be started again
    #             #  eventhough it is cancelled. Basically, the result will never
    #             #  be set, but the acquisition can still be going on indefinitely.


class SignalLauncherAcquisitionModule(SignalLauncher):
    """ class that takes care of emitting signals to update all possible
    displays"""

    display_curve = QtCore.Signal(list)  # This signal is emitted when
    # curves need to be displayed the argument is [array(times),
    # array(curve1), array(curve2)] or [times, None, array(curve2)]
    autoscale_x = QtCore.Signal()

    # For now, the following signals are only implemented with NA.
    update_point = QtCore.Signal(int)  #  used in NA only
    scan_finished = QtCore.Signal()  #  used in NA only
    clear_curve = QtCore.Signal()  #  NA only
    x_log_toggled = QtCore.Signal() #  logscale changed

    # Following signal only implemented in spec an
    unit_changed = QtCore.Signal()


class AcquisitionModule(Module):
    """
    The asynchronous mode is supported by a sub-object "run"
    of the module. When an asynchronous acquisition is running
    and the widget is visible, the current averaged data are
    automatically displayed. Also, the run object provides a
    function save_curve to store the current averaged curve
    on the hard-drive.

    The full API of the "run" object is the following.

    Methods:

        *(All methods return immediately)*
        single(): performs an asynchronous acquisition of trace_average curves.
            The function returns a promise of the result:
            an object with a ready() function, and a get() function that
            blocks until data is ready.
        continuous(): continuously acquires curves, and performs a
            moving average over the trace_average last ones.
        pause(): stops the current acquisition without restarting the
            averaging
        stop(): stops the current acquisition and restarts the averaging.
        save_curve(): saves the currently averaged curve (or curves for scope)
        curve(): the currently averaged curve

    Attributes:

        curve_name (str): name of the curve to create upon saving
        trace_average (int): number of averages in single (not to confuse with
            averaging per point)
        data_avg (array of numbers): array containing the current averaged curve
        current_avg (int): current number of averages

    """
    # The averaged data are stored in a RunFuture object _run_future
    #
    # _setup() recreates from scratch _run_future by calling _new_run_future()
    #
    # It is necessary to setup the AcquisitionModule on startup to start
    # with clean arrays
    #
    # Changing any attribute in callback_attribute (mostly every
    # setup_attribute except running_state) will force a restart of the
    # averaging by calling setup
    #
    # On the other hand, "running_state" has a customized behavior: it will
    # only call setup() when needed and perform customized actions otherwise:
    #  - paused/stopped -> running_single: start acquisition on new future
    #  - paused -> running_continuous: start acquisition on same future + set
    #  future to run_continuous (irreversible)
    #  - stopped -> running_continuous: start acquisition on new future +
    # set future to run_continuous (irreversible) == call setup()
    #  - running_single/running_continuous -> pause/stop: pause acquisition

    _gui_attributes = ['trace_average', 'curve_name']

    _setup_on_load = True #  acquisition_modules need to be setup() once
    # they are loaded
    _signal_launcher = SignalLauncherAcquisitionModule
    _setup_attributes = ['trace_average', 'curve_name', '_running_state']

    MIN_DELAY_SINGLE_MS = 0  # async acquisition should be as fast as
    # possible
    MIN_DELAY_CONTINUOUS_MS = 40  # leave time for the event loop in
    # continuous

    # the real settable property is _running_state, running_state is read_only
    # for the user
    _running_state = SelectProperty(
        default='stopped',
        options=["running_single",
                 "running_continuous",
                 "paused_single",
                 "paused_continuous",
                 "stopped"],
        doc="Indicates whether the instrument is running acquisitions or not. "
            "See :class:`RunningStateProperty` for available options. ")

    @property
    def running_state(self):
        return self._running_state

    trace_average = IntProperty(doc="number of curves to average in single mode. In "
                           "continuous mode, a moving window average is "
                           "performed.",
                           default=1,
                           min=1)
    curve_name = StringProperty(doc="name of the curve to save.")

    def __init__(self, parent, name=None):
        # The curve promise is initialized with a dummy Future, because
        # instantiating CurveFuture launches a curve acquisition
        #self._curve_future = Future()

        super(AcquisitionModule, self).__init__(parent, name=name)
        self._last_run = None
        self.curve_name = self.name + " curve"
        self.current_avg = 0
        #self._run_future = self._run_future_cls(self,
        #
        # min_delay_ms=self.MIN_DELAY_SINGLE_MS)
        # On the other hand, RunFuture has a start method and is not started
        # at instanciation.

    def _emit_signal_by_name(self, signal_name, *args, **kwds):
        """Let's the module's signal_launcher emit signal name"""
        self._signal_launcher.emit_signal_by_name(signal_name, *args, **kwds)

    async def _trace_async(self, min_delay_ms):
        """
        Same as curve_async except this function can be used in any
        running_state.
        """
        self._start_trace_acquisition()
        await self._data_ready_async(min_delay_ms)
        return self._get_trace()

    # def curve_async(self):
    #     """
    #     Launches the acquisition for one curve with the current parameters.
    #
    #     - If running_state is not "stopped", stops the current acquisition.
    #     - If rolling_mode is True, raises an exception.
    #     - Immediately returns a future object representing the curve.
    #     - The curve can be retrieved by calling result(timeout) on the future object.
    #     - The future is cancelled if the instrument's state is changed before the end of the acquisition, or another call to curve_async() or curve() is made on the same instrument.
    #     """
    #     if self.running_state is not "stopped":
    #         self.stop()
    #     return ensure_future(self._curve_async(0))

    # def trace(self, timeout=None):
    #     """
    #     Same as curve_async, except:
    #
    #     - the function will not return until the curve is ready or timeout occurs.
    #     - the function directly returns an array with the curve instead of a future object
    #     """
    #     return wait(self._trace_async(0), timeout=timeout)
    #     # return self.curve_async().await_result(timeout)

    def single_async(self):
        """
        Performs an asynchronous acquisition of trace_average curves.

        - If running_state is not stop, stops the current acquisition.
        - Immediately returns a future object representing the curve.
        - The curve can be retrieved by calling result(timeout) on the future object.
        - The future is cancelled if the instrument's state is changed before the end of the acquisition.
        """
        #self.running_state = 'running_single'
        #return self._run_future

        self._running_state = 'running_single'
        self._prepare_averaging()  # initializes the table self.data_avg,
        return self._renew_run(self._single_async())

    async def _data_ready_async(self, min_delay_s):
        """
        sleeps remaining time (or min_delay_s if too short) untill
        self._data_ready becomes eventually True.
        """
        await sleep(max(self._remaining_time(), min_delay_s))
        while not self._data_ready():
            await sleep(max(self._remaining_time(), min_delay_s))

    async def _single_async(self):
        # and self.current_avg
        while self.current_avg < self.trace_average:
            self.current_avg+=1
            if self.running_state=='paused_single':
                await self._resume_event.wait()
            #if self.running_state=='stopped': # likely useless but doesn't
                # hurt
            #    raise ValueError("Acquisition was stopped")
            self.data_avg = (self.data_avg * (self.current_avg-1) + \
                             await self._trace_async(0)) / self.current_avg
            self._emit_signal_by_name('display_curve', [self.data_x,
                                                        self.data_avg])
        self._running_state = 'stopped'
        return self.data_avg

    def _renew_run(self, coro):
        if self._last_run is not None:
            self._last_run.cancel()
        self._last_run = ensure_future(coro)
        return self._last_run

    def single(self, timeout=None):
        """
        Same as single_async, except:
            - the function will not return until the averaged curve is ready or timeout occurs.
            - the function directly returns an array with the curve instead of a future object.
        """
        #return self.single_async().await_result(timeout)
        self._running_state = 'running_single'
        self._prepare_averaging()  # initializes the table self.data_avg,
        return wait(self._renew_run(self._single_async()), timeout=timeout)

    async def _continuous_async(self):
        while(self.running_state!='stopped'):
            if self.running_state=='paused_continuous':
                await self._resume_event.wait()
            self.current_avg = min(self.current_avg + 1, self.trace_average)
            self.data_avg = (self.data_avg * (self.current_avg-1) + \
                             await self._trace_async(self.MIN_DELAY_CONTINUOUS_MS * 0.001)) / \
                            self.current_avg
            self._emit_signal_by_name('display_curve', [self.data_x,
                                                        self.data_avg])

    def continuous(self):
        """
        continuously acquires curves, and performs a moving
        average over the trace_average last ones.
        """
        self._running_state = 'running_continuous'
        self._prepare_averaging()  # initializes the table self.data_avg,
        self._renew_run(self._continuous_async())
        # self.running_state = 'running_continuous'
        # return self._continuous_future

    def pause(self):
        """
        Stops the current acquisition without restarting the averaging
        """
        if self.running_state=='running_single':
            self._running_state = 'paused_single'
        if self.running_state=='running_continuous':
            self._running_state = 'paused_continuous'
        self._resume_event = Event()
        self._free_up_resources()

    def resume(self):
        """
        Resume the current averaging run. the future returned by a previous
        call of single_async will eventually be set at the end.
        """
        if not self.running_state in ['paused_single', 'paused_continuous']:
            raise ValueError("resume can only be called in 'paused' state.")
        self._resume_event.set()

    def _resume_new_single(self): # mostly for gui usage
        """
        Resume averaging at the current state in single mode
        Beware, a future returned by a previous call of single_async will
        be cancelled.
        """
        if not self.running_state in ['paused_single', 'paused_continuous']:
            raise ValueError("resume can only be called in 'paused' state.")
        self._running_state = 'running_single'
        # self._prepare_averaging()  # initializes the table self.data_avg,
        return self._renew_run(self._single_async())

    def _resume_new_continuous(self): # mostly for gui usage
        """
        Resume averaging at the current state in continuous mode.
        Of course, a future returned by a previous call of single_async will
        be cancelled.
        """
        if not self.running_state in ['paused_single', 'paused_continuous']:
            raise ValueError("resume can only be called in 'paused' state.")
        self._running_state = 'running_continuous'
        # self._prepare_averaging()  # initializes the table self.data_avg,
        return self._renew_run(self._continuous_async())

    def stop(self):
        """
        Stops the current acquisition and averaging will be restarted
        at next run.
        """
        if self._last_run is not None:
            self._last_run.cancel()
        self._running_state = 'stopped'
        self._free_up_resources()

    def save_curve(self):
        """
        Saves the curve(s) that is (are) currently displayed in the gui in
        the db_system. Also, returns the list [curve_ch1, curve_ch2]...
        """
        params = self.attributes_last_run
        self.attributes_last_run.update(name=self.curve_name)
        curve = self._save_curve(self.data_x,
                                 self.data_avg,
                                 **params)
        return curve

    def _clear(self):
        super(AcquisitionModule, self)._clear()
        if self._last_run:
            self._last_run.cancel()

    def _setup(self):
        """

        :return:
        """

        # the _run_future is renewed to match the requested type of run (
        # rolling_mode or triggered)
        # This is how we make sure changing duration or rolling_mode won't
        # freeze the acquisition.
        #self._new_run_future()
        if self.running_state in ['running_single',
                                  'paused_single',
                                  'paused_continuous',
                                  'stopped']:
            self.stop()
        if self.running_state=='running_continuous':
            self.continuous()
        #     self.single_async()
        # if self.running_state=='running_continuous':
        #     self.continuous()
        # if self.running_state=='stopped':
        #     self.stop()

    # Methods to implement in derived class:
    # --------------------------------------

    def _remaining_time(self):
        """
        remaining time (in seconds) until the data has a chance to be ready.
        In the case of scope, where trigger might delay the acquisition,
        this is the minimum time to wait in the "best case scenario" where
        the acquisition would have started immediately after setup().
        """
        raise NotImplementedError("To implement in derived class")  # pragma: no cover

    def _data_ready(self):
        """
        :return: True or False
        """
        raise NotImplementedError('To implement in derived class')  # pragma: no cover

    def _get_trace(self):
        """
        get the curve from the instrument.
          a 1D array for single channel instruments
          a 2*n array for the scope
        """
        raise NotImplementedError  # pragma: no cover

    # @property
    # def data_x(self):
    #     """
    #     x-axis of the curves to plot.
    #     :return:
    #     """
    #     raise NotImplementedError("To implement in derived class")  # pragma: no cover

    def _start_trace_acquisition(self):
        """
        If anything has to be communicated to the hardware (such as make
        trigger ready...) to start the acquisition, it should be done here.
        This function will be called only be called by the init-function of
        the _curve_future()
        Only non-blocking operations are allowed.
        """
        pass  # pragma: no cover

    def _get_run_attributes(self):
        """
        This function is called when the run starts and the result is stored
        in self.attributes_last_run.
        """
        return self.setup_attributes

    def _prepare_averaging(self):
        """
        Initializes the table self.data_avg with zeros of the right dimensions.
        Also sets self.data_x to a copy of the right array (such that changing
        the setup won't affect the saved data)
        Also resets self.current_avg to 0
        Finally, save the attributes_last_run to make sure they are not
        changed afterwards
        """
        self.attributes_last_run = copy(self._get_run_attributes())
        self.current_avg = 0

    def _free_up_resources(self):
        pass # pragma: no cover

    # Shortcut to the RunFuture data (for plotting):
    # ----------------------------------------------

    #@property
    #def data_avg(self):
    #    return self._run_future.data_avg

    #@property
    #def current_avg(self):
    #    return self._run_future.current_avg
