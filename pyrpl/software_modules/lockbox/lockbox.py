from __future__ import division
from collections import OrderedDict
from qtpy import QtCore
import logging
from ...modules import SignalLauncher
from ...module_attributes import ModuleListProperty
from .input import *
from .output import *
from ...widgets.module_widgets import LockboxWidget
from ...pyrpl_utils import all_subclasses
from .stage import Stage
from . import LockboxModule, LockboxModuleDictProperty
from . import LockboxLoop, LockboxPlotLoop
from ...widgets.module_widgets.lockbox_widget import LockboxSequenceWidget
from pyrpl.async_utils import wait, sleep_async, sleep, ensure_future, Event


def all_classnames():
    return OrderedDict([(subclass.__name__, subclass) for subclass in
                                 [Lockbox] + all_subclasses(Lockbox)])


class ClassnameProperty(SelectProperty):
    """
    Lots of lockbox attributes need to be updated when model is changed
    """
    def set_value(self, obj, val):
        super(ClassnameProperty, self).set_value(obj, val)
        # we must save the attribute immediately here in order to guarantee
        # that make_Lockbox works
        if obj._autosave_active:
            self.save_attribute(obj, val)
        else:
            obj._logger.debug("Autosave of classname attribute of Lockbox is "
                              "inactive. This may have severe impact "
                              "on proper functionality.")
        obj._autosave_active = False
        obj._logger.debug("Lockbox classname changed to %s", val)
        # this call results in replacing the lockbox object by a new one
        obj._classname_changed()
        return val


class StateSelectProperty(SelectProperty):
    def set_value(self, obj, val):
        super(StateSelectProperty, self).set_value(obj, val)
        # save the last time of change of state
        obj._state_change_time = time()
        if val in ["lock_on"]:
            obj.unlock_event = Event()
        else:
            if obj._monitor_lock_status_task is not None:
                obj._monitor_lock_status_task.cancel()
        if not val in ["lock_on", "sweep", "unlock"]:
            obj._monitor_lock_status_task = ensure_future(
                obj._monitor_lock_status_async())
        obj._signal_launcher.state_changed.emit([val])


class SignalLauncherLockbox(SignalLauncher):
    """
    A SignalLauncher for the lockbox
    """
    output_created = QtCore.Signal(list)
    output_deleted = QtCore.Signal(list)
    output_renamed = QtCore.Signal()
    stage_created = QtCore.Signal(list)
    stage_deleted = QtCore.Signal(list)
    stage_renamed = QtCore.Signal()
    delete_widget = QtCore.Signal()
    state_changed = QtCore.Signal(list)
    add_input = QtCore.Signal(list)
    input_calibrated = QtCore.Signal(list)
    remove_input = QtCore.Signal(list)
    update_transfer_function = QtCore.Signal(list)
    update_lockstatus = QtCore.Signal(list)
    p_gain_rounded = QtCore.Signal(list)
    p_gain_ok = QtCore.Signal(list)
    i_gain_rounded = QtCore.Signal(list)
    i_gain_ok = QtCore.Signal(list)

class Lockbox(LockboxModule):
    """
    A Module that allows to perform feedback on systems that are well described
    by a physical model.
    """
    _widget_class = LockboxWidget
    _signal_launcher = SignalLauncherLockbox
    _gui_attributes = ["classname",
                       "default_sweep_output",
                       "auto_lock",
                       "is_locked_threshold",
                       "setpoint_unit"]
    _setup_attributes = _gui_attributes + [#"auto_lock_interval",
                                           "lockstatus_interval",]
                                           #"_auto_lock_timeout"]

    classname = ClassnameProperty(options=lambda: list(all_classnames().keys()))

    def __init__(self, parent, name=None):
        super(Lockbox, self).__init__(parent=parent, name=name)
        # set state change time to negative value to indicate startup condition
        self._state_change_time = -1
        self._acquire_lock_task = None
        self._monitor_lock_status_task = None
        self.unlock_event = Event()

    ###################
    # unit management #
    ###################
    # setpoint_unit is mandatory to specify in which unit the setpoint is given
    setpoint_unit = SelectProperty(options=['V'], default='V', ignore_errors=True)
    # output gain comes in units of '_output_unit'/V of analog redpitaya output
    _output_units = ['V', 'mV']
    # each _output_unit must come with a function that allows conversion from
    # output_unit to setpoint_unit
    def _unit1_in_unit2(self, unit1, unit2, try_prefix=True):
        """ helper function to convert unit2 to unit 1"""
        if unit1 == unit2:
            return 1.0
        try:
            return getattr(self, '_'+unit1+'_in_'+unit2)
        except AttributeError:
            try:
                return 1.0 / getattr(self, '_' + unit2 + '_in_' + unit1)
            except AttributeError:
                if not try_prefix:
                    raise
        # did not find the unit. Try scaling of unit1
        _unit_prefixes = OrderedDict([('', 1.0,),
                                      ('m', 1e-3),
                                      ('u', 1e-6),
                                      ('n', 1e-9),
                                      ('p', 1e-12),
                                      ('k', 1e3),
                                      ('M', 1e6),
                                      ('G', 1e9),
                                      ('T', 1e12)])
        for prefix2 in _unit_prefixes:
            if unit2.startswith(prefix2) and len(unit2)>len(prefix2):
                for prefix1 in _unit_prefixes:
                    if unit1.startswith(prefix1) and len(unit1)>len(prefix1):
                        try:
                            return self._unit1_in_unit2(unit1[len(prefix1):],
                                                         unit2[len(prefix2):],
                                                         try_prefix=False)\
                                   * _unit_prefixes[prefix1]\
                                   / _unit_prefixes[prefix2]
                        except AttributeError:
                            pass
        raise AttributeError("Could not find attribute %s in Lockbox class. "
                             %(unit1+'_in_'+unit2))

    def _unit_in_setpoint_unit(self, unit):
        # helper function to convert setpoint_unit into unit
        return self._unit1_in_unit2(unit, self.setpoint_unit)

    def _setpoint_unit_in_unit(self, unit):
        # helper function to convert setpoint_unit into unit
        return self._unit1_in_unit2(self.setpoint_unit, unit)

    # default_sweep_output would throw an error if the saved state corresponds
    # to a nonexisting output
    default_sweep_output = SelectProperty(options=lambda lb: lb.outputs.keys(),
                                          ignore_errors=True)

    # consider cavity locked ifin units of setpoint_unit
    is_locked_threshold = FloatProperty(default=1.0, min=-1e10, max=1e10,
                                        doc="Setpoint interval size to consider "
                                            "system in locked state")


    auto_lock = BoolProperty(default=False, doc="Turns on the autolock "
                                                    "of the module.")

    lock_status = BoolProperty(default=False,
                               doc="Is the current stage properly locked ?"
                                   "based on the last call of is_locked")

    lockstatus_interval = FloatProperty(default=1.0,
                                                     min=1e-3,
                                                     max=1e10)

    # logical inputs and outputs of the lockbox are accessible as
    # lockbox.outputs.output1
    inputs = LockboxModuleDictProperty(input_from_output=InputFromOutput)
    outputs = LockboxModuleDictProperty(output1=OutputSignal)

    # Sequence is a list of stage modules. By default the first stage is created
    sequence = ModuleListProperty(Stage, default=[{}])
    sequence._widget_class = LockboxSequenceWidget

    # current state of the lockbox
    current_state = StateSelectProperty(options=
                                          (lambda inst:
                                            ['unlock', 'sweep',
                                             'lock_on']
                                            + list(range(len(inst.sequence)))),
                                        default='unlock')


    def _current_stage(self, state=None):
        if state is None:
            state = self.current_state
        if self.current_state=="lock_on":
            state = self.sequence[-1]
        if isinstance(state, int):
            return self.sequence[self.current_state]
        else:
            return state

    @property
    def current_stage(self):
        return self._current_stage()

    @property
    def signals(self):
        """ a dict of all logical signals of the lockbox """
        # only return those signals that are already initialized to avoid
        # recursive loops at startup
        signallist = []
        if hasattr(self, "_inputs"):
            signallist += self.inputs.items()
        if hasattr(self, "_outputs"):
            signallist += self.outputs.items()
        return OrderedDict(signallist)
        #return OrderedDict(self.inputs.items()+self.outputs.items())

    @property
    def asg(self):
        """ the asg being used for sweeps """
        if not hasattr(self, '_asg') or self._asg is None:
            self._asg = self.pyrpl.asgs.pop(self.name)
        return self._asg

    def calibrate_all(self, autosave=False):
        """
        Calibrates successively all inputs
        """
        curves = []
        for input in self.inputs:
            try:
                c = input.calibrate(autosave=autosave)
                if c is not None:
                    curves.append(c)
            except BaseException as e:
                print(e)
        return curves

    def get_analog_offsets(self, duration=1.0):
        """
        Measures and saves the analog offset for all inputs.

        This function is designed to measure the analog offsets of the redpitaya
        inputs and possibly the sensors connected to these inputs. Only call this
        function if you are sure about what you are doing and if all signal sources
        (lasers etc.) are turned off.

        The parameter duration specifies the time during which to average the
        input offsets.
        """
        for input in self.inputs:
            input.get_analog_offset(duration=duration)

    def unlock(self, reset_offset=True):
        """
        Unlocks all outputs.
        """
        if self._acquire_lock_task is not None:  # stop locking sequence
            # print("cancel acquire")
            self._acquire_lock_task.cancel()
        for output in self.outputs:
            output.unlock(reset_offset=reset_offset)
        self.current_state = 'unlock'

    def _sweep(self):
        """
        Performs a sweep of one of the output. No output default kwds to avoid
        problems when use as a slot.
        """
        self.unlock()
        self.outputs[self.default_sweep_output].sweep()
        self.current_state = "sweep"

    def sweep(self):
        """
        Performs a sweep of one of the output. No output default kwds to avoid
        problems when use as a slot.
        """
        return self._sweep()

    async def _monitor_lock_status_async(self):
        while not self.current_state in ["unlock", "sweep"]:
            new_status = self.is_locked()
            if self.current_state=="lock_on" and not new_status:#elf.lock_status:
                if not self.unlock_event.is_set():
                    self.unlock_event.set()
                    self.unlock_event = Event()
                if self.auto_lock:
                    self.lock_async()
            self.lock_status = new_status
            self._signal_launcher.update_lockstatus.emit([new_status])
            # optionally, call logging functionality implemented derived classes here...
            try: self.log_lockstatus()
            except AttributeError: pass
            await sleep_async(self.lockstatus_interval)

    async def _lock_async(self, retry_times=1, **kwds):
        """
        Launches the full lock sequence, stage by stage until the end.
        optional kwds are stage attributes that are set after iteration through
        the sequence, e.g. a modified setpoint.
        retry_times is used to specify the number of tries. 1 means,
        only one try is allowed, 0 means infinite retries.
        """
        # iterate through locking sequence:
        # unlock -> sequence
        #self.unlock()
        # modify last stage according to provided kwds
        current_try = 0
        while retry_times==0 or current_try<retry_times:
            for stage in self.sequence:
                await stage._execute_async()
            if self.is_locked():
                return True
            current_try+=1
        return False
        # self.final_stage.enable()

    def lock_async(self, retry_times=1, **kwds):
        """
        Launches the full lock sequence, stage by stage until the end.
        optional kwds are stage attributes that are set after iteration through
        the sequence, e.g. a modified setpoint.
        """
        self._acquire_lock_task = ensure_future(self._lock_async(
            retry_times=retry_times, **kwds))
        return self._acquire_lock_task

    def lock(self, timeout=None, retry_times=1, **kwds):
        """
        Same as lock_async except it only returns a boolean at the end of the
        lock sequence.
        """
        return wait(self.lock_async(retry_times=retry_times,
                                    timeout=timeout, **kwds))

    def sleep_while_locked(self, time_to_sleep):
        """
        wait for time_to_sleep and returns True if no unlock occured.
        Otherwise, returns False as soon as unlock occurs.
        """
        if self.current_state=="lock_on" and self.is_locked():
            try:
                res = wait(ensure_future(self.unlock_event.wait()),
                           timeout=time_to_sleep)
            except TimeoutError:
                return True
            else:
                return False
        else:
            self._logger.error('Error during measurement - cavity unlocked. Aborting sleep...')
            return False

    def is_locked(self, input=None, loglevel=logging.INFO):
        """ returns True if locked, else False. Also updates an internal
        dict that contains information about the current error signals. The
        state of lock is logged at loglevel """
        if not self.current_stage in self.sequence:
            # not locked to any defined sequence state
            self._logger.log(loglevel,
                             "Not locked: lockbox state '%s' does not "
                             "correspond to a lock stage.",
                             self.current_state)
            return False
        # test for output saturation
        for o in self.outputs:
            if o.is_saturated:
                self._logger.log(loglevel, "Not locked: output %s "
                                           "is saturated.", o.name)
                return False
        # input locked to
        if input is None:
            if hasattr(self, '_default_is_locked_input') and self._default_is_locked_input is not None and self._default_is_locked_input in self.inputs:
                input = self._default_is_locked_input
            else:
                input = self.current_stage.input
        if not isinstance(input, InputSignal):
            input = self.inputs[input]
        # call is_locked of the input
        try:
            return input.is_locked(loglevel=loglevel)
        except TypeError: # occurs if is_locked takes no argument loglevel
            return input.is_locked()

    def is_locked_and_final(self, loglevel=logging.INFO):
        return (self.current_state == self.sequence[-1] and
                self.is_locked(loglevel=loglevel))

    @classmethod
    def _make_Lockbox(cls, parent, name):
        """ returns a new Lockbox object of the type defined by the classname
        variable in the config file"""
        # identify class name
        try:
            classname = parent.c[name]['classname']
        except KeyError:
            classname = cls.__name__
            parent.logger.debug("No config file entry for classname found. "
                                "Using class '%s'.", classname)
        parent.logger.debug("Making new Lockbox with class %s. ", classname)
        # return instance of the class
        return all_classnames()[classname](parent, name)

    def _classname_changed(self):
        # check whether a new object must be instantiated and return if not
        if self.classname == type(self).__name__:
            self._logger.debug("Lockbox classname not changed: - formerly: %s, "
                               "now: %s.",
                              type(self).__name__,
                              self.classname)
            self._autosave_active = True
            return
        self._logger.debug("Lockbox classname changed - formerly: %s, now: %s.",
                          type(self).__name__,
                          self.classname)
        # save names such that lockbox object can be deleted
        pyrpl, name = self.pyrpl, self.name
        # launch signal for widget deletion
        self._signal_launcher.delete_widget.emit()
        # delete former lockbox (free its resources)
        self._clear()
        # Make sure that the former lockbox won't mess up with pyrpl
        # (in case the user has kept a reference to it)
        self.parent = None
        # make a new object
        new_lockbox = Lockbox._make_Lockbox(pyrpl, name)
        new_lockbox._classname = self.classname
        # update references
        setattr(pyrpl, name, new_lockbox)  # pyrpl.lockbox = new_lockbox
        pyrpl.software_modules.append(new_lockbox)
        # create new dock widget
        for w in pyrpl.widgets:
            w.reload_dock_widget(name)

    def _clear(self):
        """ returns a new Lockbox object of the type defined by the classname
        variable in the config file"""
        pyrpl, name = self.pyrpl, self.name
        if self._acquire_lock_task is not None:  # stop any lock sequence in place
            self._acquire_lock_task.cancel()
        if self._monitor_lock_status_task is not None:  # stop any lock
            # sequence in place
            self._monitor_lock_status_task.cancel()

        super(Lockbox, self)._clear()
        setattr(pyrpl, name, None)  # pyrpl.lockbox = None
        try:
            self.parent.software_modules.remove(self)
        except ValueError:
            self._logger.warning("Could not find old Lockbox %s in the list of "
                                 "software modules. Duplicate lockbox objects "
                                 "may coexist. It is recommended to restart "
                                 "PyRPL. Existing software modules: \n%s",
                                 self.name, str(self.parent.software_modules))
        # redirect all attributes of the old lockbox to the new/future lockbox
        # object
        def getattribute_forwarder(obj, attribute):
            lockbox = getattr(pyrpl, name)
            return getattr(lockbox, attribute)
        self.__getattribute__ = getattribute_forwarder
        def setattribute_forwarder(obj, attribute, value):
            lockbox = getattr(pyrpl, name)
            return setattr(lockbox, attribute, value)
        self.__setattr__ = setattribute_forwarder

    @property
    def _time(self):
        """ retrieves 'local' time of the lockbox """
        return time()

    @property
    def params(self):
        """
        returns a convenient dict with parameters that describe if and with
        which settings the lockbox was properly.

        params from different Pyrpl lockboxes can be merged together without
        problems if the names of the config files differ
        """
        d = dict(config=self.c._root._filename)
        for var in ['is_locked', 'is_locked_and_final', 'current_state',
                    '_state_change_time', '_time',
                    'setpoint_unit']:
            val = recursive_getattr(self, var)
            if callable(val):
                val = val()
            d[var] = val
        for o in self.inputs:
            o.stats(t=1.0)
            d[o.name+ '_mean'] = o.mean
            d[o.name + '_rms'] = o.rms
            d[o.name + '_calibration_data_min'] = o.calibration_data.min
            d[o.name + '_calibration_data_max'] = o.calibration_data.max
            if hasattr(o, 'quadrature_factor'):
                d[o.name + '_quadrature_factor'] = o.quadrature_factor
        for o in self.outputs:
            d[o.name+ '_mean'] = o.mean
            d[o.name + '_rms'] = o.rms
            d[o.name + '_pid_setpoint'] = o.pid.setpoint
            d[o.name + '_pid_p'] = o.pid.p
            d[o.name + '_pid_i'] = o.pid.i
            d[o.name + '_pid_ival'] = o.pid.ival
            d[o.name + '_pid_input'] = o.pid.input
        dd = dict()
        for k in d:
            dd[self.pyrpl.name+'_'+k]=d[k]
        return dd
