"""
Everything involving asynchronicity in acquisition instruments is in this file.

In particular, this includes getting curves and continuously averaging curves.
The main functions for curve acquisition are:

continuous: Launches a continuous acquisition and returns immediately
single_async: Launches an acquisition that will average 'trace_average' traces
              together. This function returns immediately a future object
              that can be evaluated once the curve is ready with
              future.result()
single(timeout): Launches the same acquisition but the function returns the
                 curves when it is ready (An exception is raised if timeout
                 occurs before).

Finally, the underscored version _single_async is a coroutine that can be
used in another coroutine with the await keyword.

Example:

    This example shows a typical acquisition use case where a sequence of
    n aquisitions of simultaneous oscilloscope and network analyzer traces
    are launched
    ::

        from pyrpl.async_utils import ensure_future, wait

        async def my_acquisition_routine(n):
            for i in range(n):
                print("acquiring scope")
                fut = p.rp.scope.run_single()
                print("acquiring na")
                data2 = await p.networkanalyzer.run_single()
                # both acquisitions are carried out simultaneously
                data1 = await fut
                print("loop %i"%i, data1, data2)
            return data1, data2
        data1, data2 = wait(my_acquisition_coroutine(10))

    If you are afraid of the cooutine syntax, the same can also done using the
    function wait provided in async_utils:
    ::
        from pyrpl.async_utils import wait

        def my_acquisition_routine(n):
            for i in range(n):
                print("acquiring scope")
                fut = p.rp.scope.run_single()
                print("acquiring na")
                data2 = wait(p.networkanalyzer.run_single())
                # both acquisitions are carried out simultaneously
                data1 = wait(fut)
                print("loop %i"%i, data1, data2)
            return data1, data2
        data1, data2 = my_acquisition_coroutine(10)
"""
from copy import copy
from .async_utils import ensure_future, sleep_async, wait, Event

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
        A property to indicate whether the curernt status of the instrument.
        The possible running states are
        - 'running_single': takes a single acquisition (trace_average averages).
        Acquisitions are automatically restarted until the desired number of
        averages is acquired.
        - 'running_continuous': continuously takes a acquisitions, eternally
        averages and restarts automatically.
        - 'paused_single': acquisition interrupted, but can eventually resumed.
        - 'paused_continuous': idem, the previous state being continuous
        - 'stopped': acquisition stopped, averaging will restart at next
        acquisition.

        _running_state is a private property, however running_state is a
        read-only attribute that mirrors the _running_state. The recommended
        way to change the state is to use the functions single(),
        continuous(), stop(), pause(), resume(). However, a boolean attribute
        run_continuous can be used to switch between continuous() and stopped()
        """
        super(RunningStateProperty, self).__init__(options=options, **kwargs)

    def set_value(self, obj, value):
        super(RunningStateProperty, self).set_value(obj, value)
        new_value = (value=='running_continuous')
        if obj.run_continuous!=new_value:
            obj._run_continuous = new_value # we don't want to trigger setup()
            if obj._autosave_active:
                obj.__class__.run_continuous.save_attribute(obj, new_value) # We need
            #  to save this right away


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
    When an asynchronous acquisition is running
    and the widget is visible, the current averaged data are
    automatically displayed. The data are averaged in the property
    self.data_avg. Moreover, the abcisse of the trace can be retrieved in
    self.data_x.
    A function save_curve to store the current averaged curve
    on the hard-drive.

    Methods:
        single_async(): Launches an acquisition of trace_average
        curves.
            The function returns a promise of the result:
            an object which can be
        continuous(): continuously acquires curves, and performs a
            moving average over the trace_average last ones.
        pause(): stops the current acquisition without restarting the
            averaging
        stop(): stops the current acquisition and restarts the averaging.
        save_curve(): saves the currently averaged curve (or curves for scope)

    Attributes:

        curve_name (str): name of the curve to create upon saving
        trace_average (int): number of averages in single (not to confuse with
            averaging per point)
        data_avg (array of numbers): array containing the current averaged curve
        data_x (array of numbers): containing the abciss data
        current_avg (int): current number of averages

    """

    # Changing any attribute in callback_attribute (mostly every
    # setup_attribute except _running_state) will force a restart of the
    # averaging by calling setup.
    # Calling setup will collapse ['_running_single', 'paused_single',
    # 'paused_continuous', 'stopped'] on 'stopped' and [
    # 'running_continuous'] on 'running_continuous'. This happens also upon
    # save/restore of the module state. This is done by keeping track of the
    #  boolean setup_attribute 'run_continuous'.


    _gui_attributes = ['trace_average', 'curve_name']

    _setup_on_load = True #  acquisition_modules need to be setup() once
    # they are loaded
    _signal_launcher = SignalLauncherAcquisitionModule
    _setup_attributes = ['trace_average',
                         'curve_name',
                         'run_continuous']

    MIN_DELAY_SINGLE_MS = 0  # async acquisition should be as fast as
    # possible (might block the gui, maybe increase?)
    MIN_DELAY_CONTINUOUS_MS = 40  # leave time for the event loop in
    # continuous

    # the real settable property is _running_state, running_state is read_only
    # for the user
    _running_state = RunningStateProperty(
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

    trace_average = IntProperty(doc="number of curves to average in single "
                                    "mode. In continuous mode, a moving "
                                    "window average is performed.",
                           default=1,
                           min=1)
    curve_name = StringProperty(doc="name of the curve to save.")
    run_continuous = BoolProperty(default=False,
                                  doc="Is the module in the running_state "
                                      "'running_continuous' or not. Contrary "
                                      "to 'running_state', this boolean "
                                      "property can be set, and saved/"
                                      "restored with the state of the module.",
                                  call_setup=True)


    def __init__(self, parent, name=None):
        super(AcquisitionModule, self).__init__(parent, name=name)
        self._last_run = None
        self.curve_name = self.name + " curve"
        self.current_avg = 0

    def _emit_signal_by_name(self, signal_name, *args, **kwds):
        """Let's the module's signal_launcher emit signal name"""
        self._signal_launcher.emit_signal_by_name(signal_name, *args, **kwds)

    async def _trace_async(self, min_delay_ms):
        """
        Launches the acquisition for one trace with the current parameters.
        """
        self._start_trace_acquisition()
        await self._data_ready_async(min_delay_ms)
        return self._get_trace()

    def single_async(self):
        """
        Performs an asynchronous acquisition of trace_average curves.
        - If running_state is not stop, stops the current acquisition.
        - Immediately returns a future object representing the curve.
        - The curve can be retrieved by calling future.result() when the
        result is ready, or async_utils.wait(future) to wait until then.
        - The future is cancelled if the instrument's state goes to any
        state except for 'paused_single' before the end of the acquisition.
        """
        return self._renew_run(self._single_async())

    async def _data_ready_async(self, min_delay_s):
        """
        sleeps remaining time (or min_delay_s if too short) until
        self._data_ready becomes eventually True.
        """
        await sleep_async(max(self._remaining_time(), min_delay_s))
        while not self._data_ready():
            await sleep_async(max(self._remaining_time(), min_delay_s))

    async def _do_average_single_async(self):
        """
        Accumulate averages based on the attributes self.current_avg and
        self.trace_average. This coroutine doesn't take care of
        initializing the data such that the module can go indifferently from
        ['paused_single', 'paused_continuous'] into ['running_single',
        'running_continuous'].
        """
        while self.current_avg < self.trace_average:
            self.current_avg+=1
            if self.running_state=='paused_single':
                await self._resume_event.wait()
            self.data_avg = (self.data_avg * (self.current_avg-1) + \
                             await self._trace_async(0)) / self.current_avg
            self._emit_signal_by_name('display_curve', [self.data_x,
                                                        self.data_avg])
        self._running_state = 'stopped'
        self._free_up_resources()
        return self.data_avg

    async def _single_async(self):
        """
        Coroutine to launch the acquisition of a trace_average traces.
        """
        self._running_state = 'running_single'
        self._prepare_averaging()  # initializes the table self.data_avg,
        return await self._do_average_single_async()

    def _renew_run(self, coro):
        """
        Takes care of cancelling the execution of the previous run if any,
        before scheduling the new one.
        """
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
        return wait(self._renew_run(self._single_async()), timeout=timeout)

    async def _do_average_continuous_async(self):
        """
        Accumulate averages based on the attributes self.current_avg and
        self.trace_average. This coroutine doesn't take care of
        initializing the data such that the module can go indifferently from
        ['paused_single', 'paused_continuous'] into ['running_single',
        'running_continuous'].
        """
        while (self.running_state != 'stopped'):
            if self.running_state == 'paused_continuous':
                await self._resume_event.wait()
            self.current_avg = min(self.current_avg + 1, self.trace_average)
            self.data_avg = (self.data_avg * (self.current_avg - 1) + \
                             await self._trace_async(
                                 self.MIN_DELAY_CONTINUOUS_MS * 0.001)) / \
                            self.current_avg
            self._emit_signal_by_name('display_curve', [self.data_x,
                                                        self.data_avg])

    async def _continuous_async(self):
        """
        Coroutine to launch a continuous acquisition.
        """
        self._running_state = 'running_continuous'
        self._prepare_averaging()  # initializes the table self.data_avg,
        await self._do_average_continuous_async()

    def continuous(self):
        """
        continuously acquires curves, and performs a moving
        average over the trace_average last ones (exponential decaying
        average).
        """
        self._renew_run(self._continuous_async())

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
        Resume the current averaging run. The future returned by a previous
        call of single_async will eventually be set at the end.
        """
        if not self.running_state in ['paused_single', 'paused_continuous']:
            raise ValueError("resume can only be called in 'paused' state.")
        if self.running_state=='paused_single':
            self._running_state = 'running_single'
        else:
            self._running_state = 'running_continuous'
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
        return self._renew_run(self._do_average_single_async())

    def _resume_new_continuous(self): # mostly for gui usage
        """
        Resume averaging at the current state in continuous mode.
        Of course, a future returned by a previous call of single_async will
        be cancelled.
        """
        if not self.running_state in ['paused_single', 'paused_continuous']:
            raise ValueError("resume can only be called in 'paused' state.")
        self._running_state = 'running_continuous'
        return self._renew_run(self._do_average_continuous_async())

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
        if self.run_continuous:
            self.continuous()
        else:
            self.stop()

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

    def _start_trace_acquisition(self):
        """
        If anything has to be communicated to the hardware (such as make
        trigger ready...) to start the acquisition, it should be done here.
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
