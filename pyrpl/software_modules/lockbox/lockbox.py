from __future__ import division
from ...modules import SoftwareModule, SignalLauncher
from ...attributes import SelectProperty, BoolProperty, StringProperty, ModuleProperty, ModuleContainerProperty
from .signals import *
from ...widgets.module_widgets import LockboxWidget
from ...pyrpl_utils import get_unique_name_list_from_class_list, all_subclasses, sleep
from .sequence import Sequence
from . import LockboxModule
from collections import OrderedDict
from PyQt4 import QtCore


def all_classnames():
    return OrderedDict([(subclass.__name__, subclass) for subclass in
                                 [Lockbox] + all_subclasses(Lockbox)])


class ClassnameProperty(SelectProperty):
    """
    Lots of lockbox attributes need to be updated when model is changed
    """
    def set_value(self, obj, val):
        super(ClassnameProperty, self).set_value(obj, val)
        # we must save the attribute immediately here in order to guarantee that make_Lockbox works
        if obj._autosave_active:
            self.save_attribute(obj, val)
        else:
            obj._logger.debug("Autosave of classname attribute of Lockbox is inactive. This may have severe impact "
                              "on proper functionality.")
        obj._logger.debug("Lockbox classname changed to %s", val)
        # this call results in replacing the lockbox object by a new one
        obj._classname_changed()
        return val

    def options(self, instance):
        return all_classnames().keys()

class SignalLauncherLockbox(SignalLauncher):
    """
    A SignalLauncher for the lockbox
    """
    output_created = QtCore.pyqtSignal(list)
    output_deleted = QtCore.pyqtSignal(list)
    output_renamed = QtCore.pyqtSignal()
    stage_created = QtCore.pyqtSignal(list)
    stage_deleted = QtCore.pyqtSignal(list)
    stage_renamed = QtCore.pyqtSignal()
    delete_widget = QtCore.pyqtSignal()
    state_changed = QtCore.pyqtSignal()
    add_input = QtCore.pyqtSignal(list)
    input_calibrated = QtCore.pyqtSignal(list)
    remove_input = QtCore.pyqtSignal(list)
    update_transfer_function = QtCore.pyqtSignal(list)
    update_lockstatus = QtCore.pyqtSignal(list)

    def __init__(self, module):
        super(SignalLauncherLockbox, self).__init__(module)
        self.timer_lock = QtCore.QTimer()
        self.timer_lock.timeout.connect(self.module.goto_next)
        self.timer_lock.setSingleShot(True)

        self.timer_autolock = QtCore.QTimer()
        # autolock works by periodiccally calling relock
        self.timer_autolock.timeout.connect(self.call_relock)
        self.timer_autolock.setSingleShot(True)
        self.timer_autolock.setInterval(1000.0)

        self.timer_lockstatus = QtCore.QTimer()
        self.timer_lockstatus.timeout.connect(self.call_lockstatus)
        self.timer_lockstatus.setSingleShot(True)
        self.timer_lockstatus.setInterval(5000.0)

        # start timer that checks lock status
        self.timer_lockstatus.start()

    def call_relock(self):
        self.module.relock()
        self.timer_autolock.start()

    def call_lockstatus(self):
        self.module._lockstatus()
        self.timer_lockstatus.start()

    def kill_timers(self):
        """
        kill all timers
        """
        self.timer_lock.stop()
        self.timer_autolock.stop()
        self.timer_lockstatus.stop()
    # state_changed = QtCore.pyqtSignal() # need to change the color of buttons in the widget
    # state is now a standard Property, signals are caught by the update_attribute_by_name function of the widget.


class AutoLockProperty(BoolProperty):
    """ true if autolock is enabled"""
    def set_value(self, obj, val):
        super(AutoLockProperty, self).set_value(obj=obj, val=val)
        if val:
            obj._signal_launcher.timer_autolock.start()
        else:
            obj._signal_launcher.timer_autolock.stop()


class AutoLockIntervalProperty(FloatProperty):
    """ timeout for autolock timer """
    def set_value(self, obj, val):
        super(AutoLockIntervalProperty, self).set_value(obj=obj, val=val)
        obj._signal_launcher.timer_autolock.setInterval(val*1000.0)


class Lockbox(LockboxModule):
    """
    A Module that allows to perform feedback on systems that are well described by a physical model.
    """
    _widget_class = LockboxWidget
    _signal_launcher = SignalLauncherLockbox
    _setup_attributes = ["classname",
                         "default_sweep_output",
                         "auto_lock",
                         "auto_lock_interval",
                         "error_threshold"]
    _gui_attributes = _setup_attributes

    classname = ClassnameProperty()
    parameter_name = "parameter"
    # possible units to describe the physical parameter to control e.g. ['m', 'MHz']
    # units that are allowed for this lockbox (must provide methods with name "_unit_to_V" for all units)
    _units = ['V']
    def _V_per_V(self):
        return 1.0

    auto_lock_interval = AutoLockIntervalProperty(default=1.0, min=1e-3,
                                                  max=1e10)
    default_sweep_output = SelectProperty(options=lambda lb: lb.outputs.keys())
    error_threshold = FloatProperty(default=1.0, min=-1e10,max=1e10)
    auto_lock = AutoLockProperty()

    # logical inputs and outputs of the lockbox are accessible as lockbox.outputs.output1
    inputs = ModuleContainerProperty(LockboxModule,
                                     input_from_output=InputFromOutput)
    outputs = ModuleContainerProperty(LockboxModule,
                                      output1=OutputSignal,
                                      output2=OutputSignal)
    # sequence attribute used to store the locking sequence
    sequence = ModuleProperty(Sequence)

    def _init_module(self):
        pass
        # update options of classname attribute with available lockbox types and update the value
        #self.__class__.classname.change_options(self, lambda: all_classnames().keys())
        #self.classname = type(self).__name__

    @property
    def signals(self):
        """ a dict of all logical signals of the lockbox """
        return OrderedDict(self.inputs.items() + self.outputs.items())

    @property
    def asg(self):
        """ the asg being used for sweeps """
        if not hasattr(self, '_asg') or self._asg is None:
            self._asg = self.pyrpl.asgs.pop(self.name)
        return self._asg

    def _setup(self):
        """
        Sets up the lockbox
        """
        for input in self.inputs:
            input.setup()
        for output in self.outputs:
            output._setup()

    def calibrate_all(self):
        """
        Calibrates successively all inputs
        """
        for input in self.inputs:
            input.calibrate()

    def unlock(self):
        """
        Disables autolock and unlocks all outputs, without touching the integrator value.
        """
        self.auto_lock = False
        self._signal_launcher.timer_lock.stop()
        for output in self.outputs:
            output.unlock()
        self.state = 'unlock'

    def sweep(self):
        """
        Performs a sweep of one of the output. No output default kwds to avoid
        problems when use as a slot.
        """
        self.unlock()
        for output in self.outputs:
            output.reset_ival()
        self.outputs[self.default_sweep_output].sweep()
        self.state = "sweep"

    def goto_next(self):
        """
        Goes to the stage immediately after the current one
        """
        if self.state=='sweep' or self.state=='unlock':
            index = 0
        else:
            index = self._stage_names.index(self.state) + 1
        stage = self._stage_names[index]
        self.goto(stage)
        self._signal_launcher.timer_lock.setInterval(self._get_stage(stage).duration * 1000)
        if index + 1 < len(self.sequence.stages):
            self._signal_launcher.timer_lock.start()

    def goto(self, stage_name):
        """
        Sets up the lockbox to the stage named stage_name
        """
        self._get_stage(stage_name).setup()

    def lock(self):
        """
        Launches the full lock sequence, stage by stage until the end.
        """
        self.unlock()
        self.goto_next()

    def lock_blocking(self):
        """ prototype for the blocking lock function """
        self._logger.warning("Function lock_blocking is currently not implemented correctly. ")
        self.lock()
        while not self.state == self._stage_names[-1]:
            sleep(0.01)
        return self.is_locked()

    @property
    def state(self):
        if not hasattr(self, "_state"):
            self._state = "unlock"
        return self._state

    @state.setter
    def state(self, val):
        if not val in ['unlock', 'sweep'] + [stage.name for stage in self.sequence.stages]:
            raise ValueError("State should be either unlock, or a valid stage name")
        self._state = val
        # To avoid explicit reference to gui here, one could consider using a DynamicSelectAttribute...
        self._signal_launcher.state_changed.emit()
        return val

    def is_locking_sequence_active(self):
        if self.state in self._stage_names and self._stage_names.index(
                self.state) < len(self._stage_names)-1:
            return True

    def relock(self):
        """ locks the cavity if it is_locked is false. Returns the value of
        is_locked """
        is_locked = self.is_locked(loglevel=logging.DEBUG)
        if not is_locked:
            # make sure not to launch another sequence during a locking attempt
            if not self.is_locking_sequence_active():
                self.lock()
        return is_locked

    def is_locked(self, input=None, loglevel=logging.INFO):
        """ returns True if locked, else False. Also updates an internal
        dict that contains information about the current error signals. The
        state of lock is logged at loglevel """
        if self.state not in self._stage_names:
            # not locked to any defined sequene state
            self._logger.log(loglevel, "Cavity is not locked: lockbox state "
                                       "is %s.", self.state)
            return False
        # test for output saturation
        for o in self.outputs:
            if o.is_saturated:
                self._logger.log(loglevel, "Cavity is not locked: output %s "
                                           "is saturated.", o.name)
                return False
        # input locked to
        if not input: #input=None (default) or input=False (call by gui)
            input = self._get_input(self._get_stage(self.state).input)
        try:
            # use input-specific is_locked if it exists
            try:
                islocked = input.is_locked(loglevel=loglevel)
            except TypeError: # occurs if is_locked takes no argument loglevel
                islocked = input.is_locked()
            return islocked
        except:
            pass
        # supposed to be locked at this value
        variable_setpoint = self._get_stage(self.state).variable_value
        # current values
        #actmean, actrms = self.pyrpl.rp.sampler.mean_stddev(input.input_channel)
        actmean, actrms = input.mean_rms()
        # setpoints
        setmean = input.expected_signal(variable_setpoint)
        setslope = input.expected_slope(variable_setpoint)

        # get max, min of acceptable error signals
        error_threshold = self.error_threshold
        min = input.expected_signal(variable_setpoint-error_threshold)
        max = input.expected_signal(variable_setpoint+error_threshold)
        startslope = input.expected_slope(variable_setpoint - error_threshold)
        stopslope = input.expected_slope(variable_setpoint + error_threshold)
        # no guarantee that min<max
        if max<min:
            # swap them in this case
            max, min = min, max
        # now min < max
        # if slopes have unequal signs, the signal has a max/min in the
        # interval
        if startslope*stopslope <= 0:
            if startslope > stopslope:  # maximum in between, ignore upper limit
                max = 1e100
            elif startslope < stopslope:  # minimum, ignore lower limit
                min = -1e100
        if actmean > max or actmean < min:
            self._logger.log(loglevel,
                             "Cavity is not locked: %s value "
                             "%.2f +- %.2f not in [%.2f, %.2f] "
                             "(setpoint %.2f).",
                             input.name, actmean, actrms, min, max, variable_setpoint)
            return False
        # lock seems ok
        self._logger.log(loglevel,
                         "Cavity is locked: %s value "
                         "%.2f +- %.2f (setpoint %.2f).",
                         input.name, actmean, actrms, variable_setpoint)
        return True

    def _lockstatus(self):
        """ this function is a placeholder for periodic lockstatus
        diagnostics, such as calls to is_locked, logging means and rms
        values and plotting measured setpoints etc."""
        # call islocked here for later use
        islocked = self.is_locked(loglevel=logging.DEBUG)
        islocked_color = self._is_locked_display_color(islocked=islocked)
        # ask widget to update the lockstatus display
        self._signal_launcher.update_lockstatus.emit([islocked_color])
        # optionally, call log function of the model
        try:
            self.log_lockstatus()
        except:
            pass

    def _is_locked_display_color(self, islocked=None):
        """ function that returns the color of the LED indicating
        lockstatus. If is_locked is called in update_lockstatus above,
        it should not be called a second time here
        """
        if self.state == 'sweep':
            return 'blue'
        elif self.state == 'unlock':
            return 'darkRed'
        else:
            # should be locked
            if islocked is None:
               islocked = self.is_locked(loglevel=logging.DEBUG)
            if islocked:
                if self.state == self._stage_names[-1]:
                    # locked and in last stage
                    return 'green'
                else:
                    # locked but acquiring
                    return 'yellow'
            else:
                # unlocked but not supposed to
                return 'red'

    @classmethod
    def _make_Lockbox(cls, parent, name):
        """ returns a new Lockbox object of the type defined by the classname variable in the config file"""
        # identify class name
        try:
            classname = parent.c[name]['classname']
        except KeyError:
            classname = cls.__name__
            parent.logger.debug("No config file entry for classname found. Using class '%s'.", classname)
        parent.logger.info("Making new Lockbox with class %s. ", classname)
        # return instance of the class
        return all_classnames()[classname](parent, name)

    def _classname_changed(self):
        # check whether a new object must be instantiated and return if not
        if self.classname == type(self).__name__:
            self._logger.debug("Lockbox classname not changed: - formerly: %s, now: %s.",
                              type(self).__name__,
                              self.classname)
            return
        self._logger.debug("Lockbox classname changed - formerly: %s, now: %s.",
                          type(self).__name__,
                          self.classname)
        # save names such that lockbox object can be deleted
        pyrpl, name = self.pyrpl, self.name
        # launch signal for widget deletion
        self._signal_launcher.delete_widget.emit()
        # delete former lockbox (free its resources)
        self._delete_Lockbox()
        # make a new object
        new_lockbox = Lockbox._make_Lockbox(pyrpl, name)
        # update references
        setattr(pyrpl, name, new_lockbox)  # pyrpl.lockbox = new_lockbox
        pyrpl.software_modules.append(new_lockbox)
        # create new dock widget
        for w in pyrpl.widgets:
            w.reload_dock_widget(name)

    def _delete_Lockbox(self):
        """ returns a new Lockbox object of the type defined by the classname variable in the config file"""
        pyrpl, name = self.pyrpl, self.name
        self._signal_launcher.clear()
        for o in self.outputs:
            o._clear()
        for i in self.inputs:
            i._clear()
        setattr(pyrpl, name, None)  # pyrpl.lockbox = None
        try:
            self.parent.software_modules.remove(self)
        except ValueError:
            self._logger.warning("Could not find old Lockbox %s in the list of software modules. Duplicate lockbox "
                                 "objects may coexist. It is recommended to restart PyRPL. Existing software modules: "
                                 "\n%s", self.name, str(self.parent.software_modules))
        # redirect all attributes of the old lockbox to the new/future lockbox object
        def getattribute_forwarder(obj, attribute):
            lockbox = getattr(pyrpl, name)
            return getattr(lockbox, attribute)
        self.__getattribute__ = getattribute_forwarder
        def setattribute_forwarder(obj, attribute, value):
            lockbox = getattr(pyrpl, name)
            return setattr(lockbox, attribute, value)
        self.__setattr__ = setattribute_forwarder

    def _get_stage(self, name):
        """
        retieves a stage by name
        """
        return self.sequence.get_stage(name)

    def _add_stage(self):
        """
        adds a stage to the lockbox sequence
        """
        return self.sequence.add_stage()

    def _remove_stage(self, stage):
        """
        Removes stage from the lockbox seequence
        """
        self.sequence.remove_stage(stage)

    def _rename_stage(self, stage, new_name):
        self.sequence.rename_stage(stage, new_name)

    def _remove_all_stages(self):
        self.sequence.remove_all_stages()

    @property
    def _stage_names(self):
        return self.sequence.stage_names
