from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import time
import functools

import sys
if sys.version_info < (3,):
    integer_types = (int, long)
else:
    integer_types = (int,)


class NumberSpinBox(QtGui.QWidget, object):
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
    value_changed = QtCore.pyqtSignal()
    timer_min_interval = 20 # don't go below 20 ms
    timer_initial_latency = 300 # 100 ms before starting to update
    # continuously.

    def forward_to_subspinboxes(func):
        """
        a decorator that forwards function calls to subspinboxes
        """
        # in base class, the trivial forwarder is chosen
        def func_wrapper(self, *args, **kwargs):
            return func(*args, **kwargs)
        return func_wrapper

    def __init__(self, label="", min=-1, max=1, increment=2.**(-13),
                 log_increment=False, halflife_seconds=0.1, per_second=0.2):
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
        self._val = 0  # internal storage for value with best-possible accuracy
        self.labeltext = label
        self.log_increment = log_increment
        self.minimum = min  # imitates original QSpinBox API
        self.maximum = max  # imitates original QSpinBox API
        self.halflife_seconds = halflife_seconds
        self.per_second = per_second
        self.singleStep = increment
        self.make_layout()
        self.update_tooltip()
        self.set_min_size()
        self.val = 0

    def make_layout(self):
        self.lay = QtGui.QHBoxLayout()
        self.lay.setContentsMargins(0,0,0,0)
        self.lay.setSpacing(0)
        self.setLayout(self.lay)
        if self.labeltext is not None:
            self.label = QtGui.QLabel(self.labeltext)
            self.lay.addWidget(self.label)
        if self.log_increment:
            self.up = QtGui.QPushButton('*')
            self.down = QtGui.QPushButton('/')
        else:
            self.up = QtGui.QPushButton('+')
            self.down = QtGui.QPushButton('-')
        self.lay.addWidget(self.down)
        self.line = QtGui.QLineEdit()
        self.line.setStyleSheet("QLineEdit { qproperty-cursorPosition: 0; }") # align text on the left
        # http://stackoverflow.com/questions/18662157/qt-qlineedit-widget-to-get-long-text-left-aligned
        self.lay.addWidget(self.line)
        self._button_up_down = False
        self._button_down_down = False
        self.lay.addWidget(self.up)
        self.timer_arrow = QtCore.QTimer()
        self.timer_arrow.setSingleShot(True)
        self.timer_arrow.setInterval(self.timer_min_interval)
        self.timer_arrow.timeout.connect(self.make_step_continuous)
        self.timer_arrow_latency = QtCore.QTimer()
        self.timer_arrow_latency.setInterval(self.timer_initial_latency)
        self.timer_arrow_latency.setSingleShot(True)
        self.timer_arrow_latency.timeout.connect(self.make_step_continuous)
        self.up.pressed.connect(self.first_increment)
        self.down.pressed.connect(self.first_increment)
        self.up.setMaximumWidth(15)
        self.down.setMaximumWidth(15)
        self.up.released.connect(self.timer_arrow.stop)
        self.down.released.connect(self.timer_arrow.stop)
        self.line.editingFinished.connect(self.validate)

    def set_min_size(self):
        """
        sets the min size for content to fit.
        """
        font = QtGui.QFont("", 0)
        font_metric = QtGui.QFontMetrics(font)
        pixel_wide = font_metric.width("0"*self.max_num_letter())

    def max_num_letter(self):
        """
        Returns the maximum number of letters
        """
        return 5

    def first_increment(self):
        """
        Once +/- pressed for timer_initial_latency ms, start to update continuously
        """
        if self.log_increment:
            self.last_time = time.time() # don't make a step, but store present time
            self.timer_arrow.start()
        else:
            self.last_time = None
            self.make_step(single_increment=True) # start with a single_step, then make normal sweep...
            self.timer_arrow_latency.start() # wait longer than average

    def set_log_increment(self):
        self.up.setText("*")
        self.down.setText("/")
        self.log_increment = True

    def sizeHint(self): #doesn t do anything, probably need to change sizePolicy
        return QtCore.QSize(200, 20)

    def update_tooltip(self):
        """
        The tooltip uses the values of min/max/increment...
        """
        string = "Increment is %.5f\nmin value: %.1f\nmax value: %.1f\n"%(self.singleStep, self.minimum, self.maximum)
        string+="Press up/down to tune." #  or mouse wheel
        self.setToolTip(string)

    def setDecimals(self, val):
        self.decimals = val
        self.set_min_size()

    @property
    def log_factor(self):
        """
        Factor by which value should be divide/multiplied (in log mode) given
        the wait time since last step
        """
        dt = time.time() - self.last_time # self.timer_arrow.interval()  # time since last step
        return 2.**(dt/self.halflife_seconds)

    @property
    def lin_delta(self):
        """
        Quantity to add/subtract to value (in lin mode) given the wait time since last step
        """
        dt = time.time() - self.last_time  # self.timer_arrow.interval()  # time since last step
        return dt*self.per_second

    @property
    def best_wait_time(self):
        """
        Time to wait until value should reach the next increment
        If this time is shorter than self.timer_min_interval, then, returns timer_min_interval
        """
        if self.log_increment:
            val = self.val
            if self.is_sweeping_up():
                next_val = val + np.sign(val)*self.singleStep
                factor = next_val*1./val
            if self.is_sweeping_down():
                next_val = val - np.sign(val)*self.singleStep
                factor = val*1.0/next_val
            return int(np.ceil(max(self.timer_min_interval, 1000*np.log2(factor)))) # in log mode, wait long enough
                                                                         # that next value is multiple of increment
        else:
            return int(np.ceil(max(self.timer_min_interval, self.singleStep * 1000. / self.per_second))) # in lin mode, idem

    def is_sweeping_up(self):
        return self.up.isDown() or self._button_up_down

    def is_sweeping_down(self):
        return self.down.isDown() or self._button_down_down

    def step_up(self, single_increment=False):
        if single_increment:
            self.val += self.singleStep * 1.1
            return
        if self.log_increment:
            val = self.val
            # to prevent rounding errors from blocking the increment
            res = val * self.log_factor
            if res == 0:
                res = self.singleStep / 10.
            else:
                res += np.sign(val)*self.singleStep / 10.
            self.val = res  # self.log_step**factor
        else:
            res = self.val + self.lin_delta + self.singleStep / 10.
            self.val = res

    def step_down(self, single_increment=False):
        if single_increment:
            self.val -= self.singleStep * 1.1
            return
        if self.log_increment:
            val = self.val
            res = val / self.log_factor
            if res == 0:
                res = - self.singleStep / 10.0
            else:
                res -= np.sign(val)*self.singleStep / 10.
            self.val = res
        else:
            res = self.val - self.lin_delta - self.singleStep / 10.
            self.val = res

    def make_step_continuous(self):
        """
        :return:
        """
        # 19/6 LN: removed this because not needed any more apparently
        #sleep(1e-4) # Ugly, but has to be there, otherwise,
        # it could
        # be that this function is called forever
        # because it takes the priority over released signal...
        if self.last_time is None:
            self.last_time = time.time()
        if self.is_sweeping_down() or self.is_sweeping_up():
            self.make_step()
            self.last_time = time.time()
            self.timer_arrow.setInterval(self.best_wait_time)
            self.timer_arrow.start()

    def make_step(self, single_increment=False):
        if self.is_sweeping_up():
            self.step_up(single_increment=single_increment)
        if self.is_sweeping_down():
            self.step_down(single_increment=single_increment)
        self.validate()

    def validate(self):
        if self.line.isModified():  # otherwise don't trigger anything
            if self.val > self.maximum:
                self.val = self.maximum
            if self.val < self.minimum:
                self.val = self.minimum
            self.value_changed.emit()

    def set_per_second(self, val):
        self.per_second = val

    def setMaximum(self, val):  # imitates original QSpinBox API
        self.maximum = val
        self.update_tooltip()

    def setMinimum(self, val):  # imitates original QSpinBox API
        self.minimum = val
        self.update_tooltip()

    def setSingleStep(self, val):  # imitates original QSpinBox API
        self.singleStep = val

    def setValue(self, val):  # imitates original QSpinBox API
        """ replace this function with something useful in derived classes """
        self.val = val

    def value(self):  # imitates original QSpinBox API
        """ replace this function with something useful in derived classes """
        return self.val

    def keyPressEvent(self, event):
        if not event.isAutoRepeat():
            if event.key() == QtCore.Qt.Key_Up:
                self._button_up_down = True
                self.first_increment()
            if event.key() == QtCore.Qt.Key_Down:
                self._button_down_down = True
                self.first_increment()
        return super(NumberSpinBox, self).keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            if event.key() == QtCore.Qt.Key_Up:
                self._button_up_down = False
                self.timer_arrow.stop()
            if event.key() == QtCore.Qt.Key_Down:
                self._button_down_down = False
                self.timer_arrow.stop()
        return super(NumberSpinBox, self).keyReleaseEvent(event)

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

    @property
    def selected(self):
        return self.hasFocus()


class IntSpinBox(NumberSpinBox):
    """
    Number spin box for integer values
    """
    def __init__(self, label, min=-2**13, max=2**13, increment=1, **kwargs):
        super(IntSpinBox, self).__init__(label=label,
                                         min=min,
                                         max=max,
                                         increment=increment,
                                         **kwargs)

    @property
    def val(self):
        return int(str(self.line.text()))

    @val.setter
    def val(self, new_val):
        self.line.setText(("%.i")%round(new_val))
        self.value_changed.emit()
        return new_val

    def max_num_letter(self):
        """
        Maximum number of letters in line
        """
        return int(np.log10(self.maximum))


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
        width_in_characters = 6.5 + self.decimals
        self.setFixedWidth(width_in_characters*10)

    @property
    def val(self):
        if str(self.line.text())!=("%."+str(self.decimals) + "f")%self._val:
            return float(str(self.line.text()))
        return self._val # the value needs to be known to a precision better
        # than the display to avoid deadlocks in increments

    @val.setter
    def val(self, new_val):
        self._val = new_val # in case the line is not updated immediately
        self.line.setText(('{:.'+str(self.decimals)+'e}').format(
            float(new_val)))
        self.value_changed.emit()
        return new_val

    def max_num_letter(self):
        """
        Returns the maximum number of letters
        """
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
        self.lay = QtGui.QHBoxLayout()
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.real = FloatSpinBox(label=self.labeltext,
                                 min=self.minimum,
                                 max=self.maximum,
                                 increment=self.singleStep,
                                 log_increment=self.log_increment,
                                 halflife_seconds=self.halflife_seconds,
                                 decimals=self.decimals)
        self.imag = FloatSpinBox(label=self.labeltext,
                                 min=self.minimum,
                                 max=self.maximum,
                                 increment=self.singleStep,
                                 log_increment=self.log_increment,
                                 halflife_seconds=self.halflife_seconds,
                                 decimals=self.decimals)
        self.real.value_changed.connect(self.value_changed)
        self.lay.addWidget(self.real)
        self.label = QtGui.QLabel(" + j")
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
        else:
            return self.real.keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in [QtCore.Qt.Key_Right, QtCore.Qt.Key_Left]:
            return self.imag.keyReleaseEvent(event)
        else:
            return self.real.keyReleaseEvent(event)

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
        return self.imag.set_log_increment(*args, **kwargs)


class OldComplexSpinBox(QtGui.QFrame):
    """
    Two spinboxes representing a complex number, with the right keyboard
    shortcuts (up down for imag, left/right for real).
    """
    value_changed = QtCore.pyqtSignal()

    def __init__(self, label, min=-2**13, max=2**13, increment=1,
                 log_increment=False, halflife_seconds=0.5, decimals=4):
        super(ComplexSpinBox, self).__init__()
        self.max = max
        self.min = min
        self.decimals = decimals
        self.increment = increment
        self.log_increment = log_increment
        self.halflife = halflife_seconds
        self.label = label
        self.lay = QtGui.QHBoxLayout()
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.real = FloatSpinBox(label=label,
                                 min=min,
                                 max=max,
                                 increment=increment,
                                 log_increment=log_increment,
                                 halflife_seconds=halflife_seconds,
                                 decimals=decimals)
        self.real.value_changed.connect(self.value_changed)
        self.lay.addWidget(self.real)
        self.label = QtGui.QLabel(" + j")
        self.lay.addWidget(self.label)
        self.imag = FloatSpinBox(label=label,
                                 min=min,
                                 max=max,
                                 increment=increment,
                                 log_increment=log_increment,
                                 halflife_seconds=halflife_seconds,
                                 decimals=decimals)
        self.imag.value_changed.connect(self.value_changed)
        self.lay.addWidget(self.imag)
        self.setLayout(self.lay)
        self.setFocusPolicy(QtCore.Qt.ClickFocus)
        width_in_characters = 6.5 + self.decimals
        self.real.setFixedWidth(width_in_characters*10)
        self.imag.setFixedWidth(width_in_characters*10)

    def keyPressEvent(self, event):
        if not event.isAutoRepeat():
            if event.key() == QtCore.Qt.Key_Up:
                self.real._button_up_down = True
                self.real.first_increment()
            if event.key() == QtCore.Qt.Key_Down:
                self.real._button_down_down = True
                self.real.first_increment()
            if event.key() == QtCore.Qt.Key_Right:
                self.imag._button_up_down = True
                self.imag.first_increment()
            if event.key() == QtCore.Qt.Key_Left:
                self.imag._button_down_down = True
                self.imag.first_increment()
        return super(ComplexSpinBox, self).keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            if event.key() == QtCore.Qt.Key_Up:
                self.real._button_up_down = False
                self.real.timer_arrow.stop()
            if event.key() == QtCore.Qt.Key_Down:
                self.real._button_down_down = False
                self.real.timer_arrow.stop()
            if event.key() == QtCore.Qt.Key_Right:
                self.imag._button_up_down = False
                self.imag.first_increment()
            if event.key() == QtCore.Qt.Key_Left:
                self.imag._button_down_down = False
                self.imag.first_increment()

        return super(ComplexSpinBox, self).keyReleaseEvent(event)

    @property
    def val(self):
        return complex(self.real.val, self.imag.val)

    @val.setter
    def val(self, new_val):
        self.real.val = np.real(new_val)
        self.imag.val = np.imag(new_val)
        return new_val

    def max_num_letter(self):
        """
        Maximum number of letters in line
        """
        return self.decimals + 7

    def focusOutEvent(self, event):
        self.value_changed.emit()
        self.setStyleSheet("")

    def focusInEvent(self, event):
        self.value_changed.emit()
        self.setStyleSheet("ComplexSpinBox{background-color:red;}")

    @property
    def selected(self):
        return self.hasFocus()


class ListSpinBox(QtGui.QFrame):
    value_changed = QtCore.pyqtSignal()
    SpinBox = FloatSpinBox

    def __init__(self,
                 label,
                 min=-62.5e6,
                 max=62.5e6,
                 increment=1.,
                 log_increment=True,
                 halflife_seconds=1.,
                 spinbox = None):
        super(ListSpinBox, self).__init__()
        if spinbox is not None:
            self.SpinBox = spinbox
        self.label = label
        self.min = min
        self.max = max
        self.increment = increment
        self.halflife_seconds = halflife_seconds
        self.log_increment = log_increment
        self.lay = QtGui.QVBoxLayout()
        if label is not None:
            self.label = QtGui.QLabel(self.name)
            self.lay.addWidget(self.label)
        self.spins = []
        self.button_removes = []
        self.spin_lays = []
        #for i in range(number):
        #    self.add_spin()
        self.button_add = QtGui.QPushButton("+")
        self.button_add.clicked.connect(self.add_spin_and_select)
        self.lay.addWidget(self.button_add)
        self.lay.addStretch(1)
        self.lay.setContentsMargins(0,0,0,0)
        self.setLayout(self.lay)
        self.selected = None

    def set_increment(self, val):
        self.increment = val

    def set_maximum(self, val):
        self.max = val

    def set_minimum(self, val):
        self.min = val

    def add_spin_and_select(self):
        self.add_spin()
        #self.spins[-1].val = -1e4 -1j*1e3
        self.set_selected(-1)

    def add_spin(self):
        index = len(self.spins)
        spin = self.SpinBox(label="",
                            min=self.min,
                            max=self.max,
                            increment=self.increment,
                            log_increment=self.log_increment,
                            halflife_seconds=self.halflife_seconds,
                            decimals=5)
        self.spins.append(spin)
        spin_lay = QtGui.QHBoxLayout()
        self.spin_lays.append(spin_lay)
        spin_lay.addWidget(spin)
        button_remove = QtGui.QPushButton('-')
        self.button_removes.append(button_remove)
        spin_lay.addWidget(button_remove)
        spin.value_changed.connect(self.value_changed)
        button_remove.clicked.connect(functools.partial(self.remove_spin_and_emit, button=button_remove))
        self.lay.insertLayout(index + 1*(self.label is not None), spin_lay) #QLabel occupies the first row
        button_remove.setFixedWidth(3 * 10)

    def remove_spin_and_emit(self, button):
        self.remove_spin(button)
        self.value_changed.emit()

    def remove_spin(self, button):
        index = self.button_removes.index(button)
        button = self.button_removes.pop(index)
        spin = self.spins.pop(index)
        spin_lay = self.spin_lays.pop(index)
        self.lay.removeItem(spin_lay)
        spin.deleteLater()
        button.deleteLater()
        spin_lay.deleteLater()

    def get_list(self):
        return [spin.val for spin in self.spins]

    def set_list(self, list_val):
        for index, val in enumerate(list_val):
            if index>=len(self.spins):
                self.add_spin()
            self.spins[index].val = val
        to_delete = []
        for other_index in range(len(list_val), len(self.spins)):
            to_delete.append(self.button_removes[other_index]) # don't loop on a list that is
                                                                                 # shrinking !
        for button in to_delete:
            self.remove_spin(button)

    def editing(self):
        edit = False
        for spin in self.spins:
            edit = edit or spin.editing()
        return edit()

    def set_selected(self, index):
        if self.selected is not None:
            self.spins[self.selected].setStyleSheet("")
        self.spins[index].setFocus(True)
        self.value_changed.emit()

    def get_selected(self):
        """
        Returns the index of the selected value
        """
        for index, spin in enumerate(self.spins):
            if spin.hasFocus():
                return index


class ListFloatSpinBox(ListSpinBox):
    SpinBox = FloatSpinBox


class ListComplexSpinBox(ListSpinBox):
    SpinBox = ComplexSpinBox

