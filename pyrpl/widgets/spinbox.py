from qtpy import QtCore, QtWidgets, QtGui
import numpy as np
import time
import logging

import sys
if sys.version_info < (3,):
    integer_types = (int, long)
else:
    integer_types = (int,)


class NumberSpinBox(QtWidgets.QWidget):
    """
    Base class for spinbox with numerical value.

    The button can be either in log_increment mode, or linear increment.
       - In log_increment: the halflife_seconds value determines how long it
         takes when the user keeps clicking on the "*"/"/" buttons to change
         the value by a factor 2. Since the underlying register is assumed to
         be represented by an int, its values are separated by a minimal
         separation, called "increment". The time to wait before refreshing
         the value is adjusted automatically so that the log behavior is still
         correct, even when the value becomes comparable to the increment.
       - In linear increment, the value is immediately incremented by the
        increment, then, nothing happens during a time given by
        timer_initial_latency. Only after that the value is incremented by
        "increment" every timer_min_interval.
    """
    MOUSE_WHEEL_ACTIVATED = False
    value_changed = QtCore.Signal()
    selected = QtCore.Signal(list)
    # timeouts for updating values when mouse button / key is pessed
    change_interval = 0.02
    _change_initial_latency = 0.1 # 100 ms before starting to update continuously.
    @property
    def change_initial_latency(self):
        """ latency for continuous update when a button is pressed """
        # if sigleStep is zero, there is no need to wait for continuous update
        if self.singleStep != 0:
            return self._change_initial_latency
        else:
            return 0

    def forward_to_subspinboxes(func):
        """
        a decorator that forwards function calls to subspinboxes
        """
        # in base class, the trivial forwarder is chosen
        def func_wrapper(self, *args, **kwargs):
            return func(*args, **kwargs)
        return func_wrapper

    def __init__(self, label="", min=-1, max=1, increment=2.**(-13),
                 log_increment=False, halflife_seconds=0.5, per_second=0.2):
        """
        :param label: label of the button
        :param min: min value
        :param max: max value
        :param increment: increment of the underlying register
        :param log_increment: boolean: when buttons up/down are pressed, should the value change linearly or log
        :param halflife_seconds: when button is in log, how long to change the value by a factor 2.
        :param per_second: when button is in lin, how long to change the value by 1 unit.
        """
        super(NumberSpinBox, self).__init__(None)
        self._logger = logging.getLogger(name=__name__)
        self._val = 0  # internal storage for value with best-possible accuracy
        self.labeltext = label
        try:
            self.log_increment = log_increment
        except AttributeError:
            self._log_increment = log_increment  # for ComplexSpinbox
        self.minimum = min  # imitates original QSpinBox API
        self.maximum = max  # imitates original QSpinBox API
        try:
            self.halflife_seconds = halflife_seconds
        except AttributeError:
            self._halflife_seconds = halflife_seconds  # for ComplexSpinbox
        self.per_second = per_second
        self.singleStep = increment
        self.change_timer = QtCore.QTimer()
        self.change_timer.setSingleShot(True)
        self.change_timer.setInterval(int(np.ceil(self.change_interval*1000)))
        self.change_timer.timeout.connect(self.continue_step)
        self.make_layout()
        self.update_tooltip()
        self.set_min_size()
        self.val = 0
        self.set_halflife_seconds(self.halflife_seconds)
        self.set_per_second(self.per_second)
        self.setSingleStep(self.singleStep)

    def make_layout(self):
        self.lay = QtWidgets.QHBoxLayout()
        self.lay.setContentsMargins(0,0,0,0)
        self.lay.setSpacing(0)
        self.setLayout(self.lay)
        if self.labeltext is not None:
            self.label = QtWidgets.QLabel(self.labeltext)
            self.lay.addWidget(self.label)
        if self.log_increment:
            self.up = QtWidgets.QPushButton('*')
            self.down = QtWidgets.QPushButton('/')
        else:
            self.up = QtWidgets.QPushButton('+')
            self.down = QtWidgets.QPushButton('-')
        self.line = QtWidgets.QLineEdit()
        self.line.setStyleSheet("QLineEdit { qproperty-cursorPosition: 0; }") # align text on the left
        # http://stackoverflow.com/questions/18662157/qt-qlineedit-widget-to-get-long-text-left-aligned
        self.lay.addWidget(self.down)
        self.lay.addWidget(self.line)
        self.lay.addWidget(self.up)
        self.up.setMaximumWidth(15)
        self.down.setMaximumWidth(15)
        self.up.pressed.connect(self.first_step)
        self.down.pressed.connect(self.first_step)
        self.up.released.connect(self.finish_step)
        self.down.released.connect(self.finish_step)
        self.line.editingFinished.connect(self.validate)
        self._button_up_down = False
        self._button_down_down = False

    # keyboard interface
    def keyPressEvent(self, event):
        if not event.isAutoRepeat():
            if event.key() in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Right]:
                # ordinary value increment
                self._button_up_down = True
                self._button_down_down = False  # avoids going left & right
                self.first_step()
            elif event.key() in [QtCore.Qt.Key_Down, QtCore.Qt.Key_Left]:
                # ordinary value decrement
                self._button_down_down = True
                self._button_up_down = False  # avoids going left & right
                self.first_step()
            elif event.key() in [QtCore.Qt.Key_PageUp, QtCore.Qt.Key_PageDown]:
                # PageUp increases increment by a factor of 10
                if event.key() in [QtCore.Qt.Key_PageUp]:\
                    factor = 2
                elif event.key() in [QtCore.Qt.Key_PageDown]:
                    factor = 0.5
                else:
                    raise Exception("Unclear KeyPressEvent")
                if self.log_increment:
                    self.set_halflife_seconds(self.halflife_seconds/factor)
                    self._logger.info("Spinbox inverse halflife changed to %.2e Hz.",
                                      1./self.halflife_seconds)
                else:
                    self.set_per_second(self.per_second*factor)
                    self._logger.info("Spinbox tuning rate changed to %.2e Hz.",
                                      self.per_second)
                self.update_tooltip()
            else:
                return super(NumberSpinBox, self).keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            if event.key() in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Right]:
                self._button_up_down = False
                self.finish_step()
            elif event.key() in [QtCore.Qt.Key_Down, QtCore.Qt.Key_Left]:
                self._button_down_down = False
                self.finish_step()
            else:
                return super(NumberSpinBox, self).keyReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            pass  # no functionality so far
            # right button opens context menu for setting scanning speed etc.
            #res, okPressed = QtWidgets.QInputDialog.getDouble(self.widget.parent, "Pyrpl GUI settings", "Scanning speed", 5)
            #if okPressed:
            #    self.module._logger.warning("Number: %d", res)
        #else:
        return super(NumberSpinBox, self).mousePressEvent(event)

    @property
    def is_increasing(self):
        return self.up.isDown() or self._button_up_down

    @property
    def is_decreasing(self):
        return self.down.isDown() or self._button_down_down

    @property
    def change_sign(self):
        if self.is_increasing:
            return 1.0
        elif self.is_decreasing:
            return -1.0
        else:
            return 0.0

    def wheelEvent(self, event):
        """
        Handle mouse wheel event. No distinction between linear and log.
        :param event:
        :return:
        """
        if self.MOUSE_WHEEL_ACTIVATED:
            nsteps = int(event.delta() / 120)
            func = self.step_up if nsteps > 0 else self.step_down
            for i in range(abs(nsteps)):
                func(single_increment=True)


    # def sizeHint(self): #doesn t do anything, probably need to change
    #    # sizePolicy
    #    return QtCore.QSize(200, 20)

    def set_min_size(self):
        """
        sets the min size for content to fit.
        """
        font = QtGui.QFont("", 0)
        font_metric = QtGui.QFontMetrics(font)
        pixel_wide = font_metric.width("0"*self.max_num_letter)
        self.line.setFixedWidth(pixel_wide)

    @property
    def max_num_letter(self):
        """
        Returns the maximum number of letters
        """
        return 5

    def set_log_increment(self):
        #self.up.setText("*")
        #self.down.setText("/")
        self.up.setText(u'\u2191')  # up arrow unicode symbol
        self.down.setText(u'\u2193')  # down arrow unicode symbol
        #self.up.setStyleSheet("font-weight: italic; font-size: 8pt")
        #self.down.setStyleSheet("font-weight: bold; font-size: 8pt")
        self.log_increment = True

    def update_tooltip(self):
        """
        The tooltip uses the values of min/max/increment...
        """
        string = "Increment is %.5e\nmin value: %.1e\nmax value: %.1e\n"\
                 %(self.singleStep, self.minimum, self.maximum)
        if self.log_increment:
            string += "Tuning speed (1/halflife): %.1e Hz.\n" % (1.0/self.halflife_seconds)
        else:
            string += "Tuning speed (linear): %.1e Hz.\n" % self.per_second
        string += "Press up/down to tune.\nPress Page up/Page down to modify tuning speed." #  or mouse wheel
        self.setToolTip(string)

    def setDecimals(self, val):
        self.decimals = val
        self.set_min_size()

    def validate(self):
        """ make sure a new value is inside the allowed bounds after a
        manual change of the value """
        if self.line.isModified():
            self.setValue(self.saturate(self.val))
            self.value_changed.emit()

    def saturate(self, val):
        if val > self.maximum:
            return self.maximum
        elif val < self.minimum:
            return self.minimum
        else:
            return val

    def setMaximum(self, val):  # imitates original QSpinBox API
        self.maximum = val
        self.update_tooltip()

    def setMinimum(self, val):  # imitates original QSpinBox API
        self.minimum = val
        self.update_tooltip()

    def setSingleStep(self, val):  # imitates original QSpinBox API
        self.singleStep = val

    def set_per_second(self, val):
        self.per_second = val

    def set_halflife_seconds(self, val):
        self.halflife_seconds = val

    def setValue(self, val):  # imitates original QSpinBox API
        """ replace this function with something useful in derived classes """
        self.val = val

    def value(self):  # imitates original QSpinBox API
        """ replace this function with something useful in derived classes """
        return self.val

    # code for managing value change with buttons or keyboard
    def first_step(self):
        """
        Once +/- pressed for timer_initial_latency ms, start to update continuously
        """
        self.start_time = time.time()
        self.start_value = self.value()
        value = self.start_value + self.singleStep * self.change_sign
        if np.sign(value)*np.sign(self.start_value) < 0:
            # zero passage occured, make sure to stop at exactly 0
            value = 0
        self.setValue(self.saturate(value))
        if self.log_increment and self.start_value == 0:
            # avoid zero start_value when in log mode
            self.start_value = self.value()
        self.change_timer.start()

    def continue_step(self):
        dt = time.time() - self.start_time
        if dt > self.change_initial_latency:  # only do if pressed long enough
            if self.log_increment:
                # ensure proper behavior for zero
                if self.start_value == 0:
                    return self.first_step()  # start over when zero is crossed
                sign = self.change_sign * np.sign(self.start_value)
                halflifes = dt / self.halflife_seconds * sign
                value = self.start_value * 2 ** halflifes
                # change behavior when value is effectively zero
                if abs(value) <= self.singleStep / 2.0 and sign < 0:
                    self.start_value = 0
                    value = 0
                    self.start_time = time.time()  # ensures to stay 0 some time
            else:
                # delta for linear sweep
                value = self.start_value + self.per_second * dt * self.change_sign
                if np.sign(value) * np.sign(self.start_value) < 0:
                    # change of sign occured, make a stop at zero
                    self.start_value = 0
                    value = 0
                    self.start_time = time.time()  # ensures to stay 0 some time

            # don't do anything if the change is smaller than singleStep
            if abs(self.val - value)>self.singleStep:
                self.setValue(self.saturate(value))
        self.change_timer.start()

    def finish_step(self):
        self.change_timer.stop()
        if hasattr(self, 'start_time'):
            dt = time.time() - self.start_time
        else:
            dt = 0
        if dt > self.change_initial_latency:
            self.validate()  # make sure we validate if continue_step was on


class IntSpinBox(NumberSpinBox):
    """
    Number spin box for integer values
    """
    def __init__(self, label, min=-2**13, max=2**13, increment=1,
                 per_second=10, **kwargs):
        super(IntSpinBox, self).__init__(label=label,
                                         min=min,
                                         max=max,
                                         increment=increment,
                                         per_second=per_second,
                                         **kwargs)

    @property
    def val(self):
        return int(str(self.line.text()))

    @val.setter
    def val(self, new_val):
        self.line.setText(("%.i")%round(new_val))
        self.value_changed.emit()
        return new_val

    @property
    def max_num_letter(self):
        """
        Maximum number of letters in line
        """
        if np.isinf(self.maximum):
            return super(IntSpinBox, self).max_num_letter
        else:
            return int(np.log10(np.abs(self.maximum))+1)

    def setMaximum(self, val):  # imitates original QSpinBox API
        super(IntSpinBox, self).setMaximum(val)
        self.set_min_size()  # changes with maximum


class FloatSpinBox(NumberSpinBox):
    """
    Number spin box for float values
    """
    def __init__(self, label, decimals=4, min=-1, max=1,
                 increment=2.**(-13), **kwargs):
        self.decimals = decimals
        super(FloatSpinBox, self).__init__(label=label,
                                           min=min,
                                           max=max,
                                           increment=increment,
                                           **kwargs)

    @property
    def val(self):
        if str(self.line.text())!=("%."+str(self.decimals) + "e")%self._val:
            return float(str(self.line.text()))
        return self._val # the value needs to be known to a precision better
        # than the display to avoid deadlocks in increments

    @val.setter
    def val(self, new_val):
        # We have a cached value _val that gives finer control over the
        # value than what is displayed. In this way, clicking up/down can
        # change the value without apparent changes of the display.
        self._val = self.saturate(new_val)

        # block signal otherwise validate will be called there, however,
        # we want to use the cached value rather than the corase grained
        # value read-out from the lineedit.
        self.line.blockSignals(True)
        self.line.setText(('{:.'+str(self.decimals)+'e}').format(
            float(new_val)))
        self.line.blockSignals(False)

        # This will cause a write of the value to the redpitaya, and in turns
        # another read from the fpga (this function will be called a second
        # time here)
        self.value_changed.emit()
        return new_val

    @property
    def max_num_letter(self):
        """
        Returns the maximum number of letters
        """
        # example: -1.123e-23 has 7+decimals(3) letters
        return self.decimals + 7


class ComplexSpinBox(FloatSpinBox):
    """
    Two spinboxes representing a complex number, with the right keyboard
    shortcuts (up down for imag, left/right for real).
    """
    def forward_to_subspinboxes(func):
        """
        a decorator that forwards function calls to subspinboxes
        """
        # in base class, the trivial forwarder is chosen
        def func_wrapper(self, *args, **kwargs):
            return func(*args, **kwargs)
        return func_wrapper

    def __init__(self, *args, **kwargs):
        super(ComplexSpinBox, self).__init__(*args, **kwargs)

    def make_layout(self):
        self.lay = QtWidgets.QHBoxLayout()
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.real = FloatSpinBox(label=self.labeltext,
                                 min=self.minimum,
                                 max=self.maximum,
                                 increment=self.singleStep,
                                 log_increment=self._log_increment,
                                 halflife_seconds=self._halflife_seconds,
                                 decimals=self.decimals)
        self.imag = FloatSpinBox(label=self.labeltext,
                                 min=self.minimum,
                                 max=self.maximum,
                                 increment=self.singleStep,
                                 log_increment=self._log_increment,
                                 halflife_seconds=self._halflife_seconds,
                                 decimals=self.decimals)
        self.real.value_changed.connect(self.value_changed)
        self.lay.addWidget(self.real)
        self.label = QtWidgets.QLabel("+j")
        self.lay.addWidget(self.label)
        self.imag.value_changed.connect(self.value_changed)
        self.lay.addWidget(self.imag)
        self.setLayout(self.lay)
        self.setFocusPolicy(QtCore.Qt.ClickFocus)

    @property
    def val(self):
        return complex(self.real.val, self.imag.val)

    @val.setter
    def val(self, new_val):
        self.real.val = np.real(new_val)
        self.imag.val = np.imag(new_val)
        return new_val

    def keyPressEvent(self, event):
        if event.key() in [QtCore.Qt.Key_Right, QtCore.Qt.Key_Left]:
            return self.imag.keyPressEvent(event)
        elif event.key() in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Down]:
            return self.real.keyPressEvent(event)
        else:
            return super(ComplexSpinBox, self).keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in [QtCore.Qt.Key_Right, QtCore.Qt.Key_Left]:
            return self.imag.keyReleaseEvent(event)
        elif event.key() in [QtCore.Qt.Key_Up, QtCore.Qt.Key_Down]:
            return self.real.keyReleaseEvent(event)
        else:
            return super(ComplexSpinBox, self).keyReleaseEvent(event)

    def wheelEvent(self, event):
        return self.imag.wheelEvent(event)

    # forward calls to real and imaginary part
    # for function in ['set_min_size', 'update_tooltip', 'setDecimals',
    #                  'set_per_second', 'setMaximum', 'setMinimum',
    #                  'setSingleStep', 'set_log_increment']:
    def setFixedWidth(self, *args, **kwargs):
        self.real.setFixedWidth(*args, **kwargs)
        return self.imag.setFixedWidth(*args, **kwargs)

    def set_min_size(self, *args, **kwargs):
        self.real.set_min_size(*args, **kwargs)
        return self.imag.set_min_size(*args, **kwargs)

    def update_tooltip(self, *args, **kwargs):
        self.real.update_tooltip(*args, **kwargs)
        return self.imag.update_tooltip(*args, **kwargs)

    def setDecimals(self, *args, **kwargs):
        self.real.setDecimals(*args, **kwargs)
        return self.imag.setDecimals(*args, **kwargs)

    def set_per_second(self, *args, **kwargs):
        self.real.set_per_second(*args, **kwargs)
        return self.imag.set_per_second(*args, **kwargs)

    def set_halflife_seconds(self, *args, **kwargs):
        self.real.set_halflife_seconds(*args, **kwargs)
        return self.imag.set_halflife_seconds(*args, **kwargs)

    @property
    def halflife_seconds(self):
        return self.imag.halflife_seconds

    def setMaximum(self, *args, **kwargs):
        self.real.setMaximum(*args, **kwargs)
        return self.imag.setMaximum(*args, **kwargs)

    def setMinimum(self, *args, **kwargs):
        self.real.setMinimum(*args, **kwargs)
        return self.imag.setMinimum(*args, **kwargs)

    def setSingleStep(self, *args, **kwargs):
        self.real.setSingleStep(*args, **kwargs)
        return self.imag.setSingleStep(*args, **kwargs)

    def set_log_increment(self, *args, **kwargs):
        self.real.set_log_increment(*args, **kwargs)
        self.imag.set_log_increment(*args, **kwargs)
        self.imag.up.setText(u'\u2192')  # right arrow unicode symbol
        self.imag.down.setText(u'\u2190')  # left arrow unicode symbol

    @property
    def log_increment(self):
        return self.imag.log_increment