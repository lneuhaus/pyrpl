"""
AttributeWidgets' hierarchy is parallel to Attribute' hierarchy
An instance attr of Attribute can create its AttributeWidget counterPart by calling attr.create_widget(name, parent)
"""

from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import time
import functools
import pyqtgraph as pg
from ..pyrpl_utils import Bijection, recursive_setattr, recursive_getattr
from ..curvedb import CurveDB

import sys
if sys.version_info < (3,):
    integer_types = (int, long)
else:
    integer_types = (int,)


APP = QtGui.QApplication.instance()
if APP is None:
    APP = QtGui.QApplication(["redpitaya_gui"])


class MyNumberSpinBox(QtGui.QWidget, object):
    """
    The button can be either in log_increment mode, or linear increment.
       - In log_increment: the halflife_seconds value determines how long it takes, when the user stays clicked
         on the "*"/"/" buttons to change the value by a factor 2. Since the underlying register is assumed to be
         represented by an int, its values are separated by a minimal separation, called "increment". The time to
         wait before refreshing the value is adjusted automatically so that the log behavior is still correct, even
         when the value becomes comparable to the increment.
       - In linear increment, the value is immediately incremented by the increment, then, nothing happens during
        a time given by timer_initial_latency. Only after that, is the value incremented of "increment" every
        timer_min_interval.
    """
    MOUSE_WHEEL_ACTIVATED = False
    value_changed = QtCore.pyqtSignal()
    timer_min_interval = 20 # don't go below 20 ms
    timer_initial_latency = 500 # 100 ms before starting to update continuously.

    def __init__(self, label, min=-1, max=1, increment=2.**(-13),
                 log_increment=False, halflife_seconds=1., per_second=0.2):
        """
        :param label: label of the button
        :param min: min value
        :param max: max value
        :param increment: increment of the underlying register
        :param log_increment: boolean: when buttons up/down are pressed, should the value change linearly or log
        :param halflife_seconds: when button is in log, how long to change the value by a factor 2.
        :param per_second: when button is in lin, how long to change the value by 1 unit.
        """
        super(MyNumberSpinBox, self).__init__(None)
        self.min = min
        self.max = max
        self.increment = increment
        self.update_tooltip()
        self._val = 0
        self.halflife_seconds = halflife_seconds
        self.log_increment = log_increment
        self.per_second = per_second

        self.lay = QtGui.QHBoxLayout()
        self.lay.setContentsMargins(0,0,0,0)
        self.lay.setSpacing(0)
        self.setLayout(self.lay)

        if label is not None:
            self.label = QtGui.QLabel(label)
            self.lay.addWidget(self.label)
        self.increment = increment

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
        self.val = 0

        self.set_min_size()

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

    def wheelEvent(self, event):
        """
        Handle mouse wheel event. No distinction between linear and log.
        :param event:
        :return:
        """
        if self.MOUSE_WHEEL_ACTIVATED:
            nsteps = int(event.delta()/120)
            func = self.step_up if nsteps>0 else self.step_down
            for i in range(abs(nsteps)):
                func(single_increment=True)

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
        string = "Increment is %.5f\nmin value: %.1f\nmax value: %.1f\n"%(self.increment, self.min, self.max)
        string+="Press up/down to tune." #  or mouse wheel
        self.setToolTip(string)

    def setMaximum(self, val):
        self.max = val
        self.update_tooltip()

    def setMinimum(self, val):
        self.min = val
        self.update_tooltip()

    def setSingleStep(self, val):
        self.increment = val

    def setValue(self, val):
        self.val = val

    def setDecimals(self, val):
        self.decimals = val
        self.set_min_size()

    def value(self):
        return self.val

    def log_factor(self):
        """
        Factor by which value should be divide/multiplied (in log mode) given the wait time since last step
        """
        dt = time.time() - self.last_time # self.timer_arrow.interval()  # time since last step
        return 2.**(dt/self.halflife_seconds)

    def lin_delta(self):
        """
        Quantity to add/subtract to value (in lin mode) given the wait time since last step
        """
        dt = time.time() - self.last_time  # self.timer_arrow.interval()  # time since last step
        return dt*self.per_second

    def best_wait_time(self):
        """
        Time to wait until value should reach the next increment
        If this time is shorter than self.timer_min_interval, then, returns timer_min_interval
        """
        if self.log_increment:
            val = self.val
            if self.is_sweeping_up():
                next_val = val + np.sign(val)*self.increment
                factor = next_val*1./val
            if self.is_sweeping_down():
                next_val = val - np.sign(val)*self.increment
                factor = val*1.0/next_val
            return int(np.ceil(max(self.timer_min_interval, 1000*np.log2(factor)))) # in log mode, wait long enough
                                                                         # that next value is multiple of increment
        else:
            return int(np.ceil(max(self.timer_min_interval, self.increment*1000./self.per_second))) # in lin mode, idem

    def is_sweeping_up(self):
        return self.up.isDown() or self._button_up_down

    def is_sweeping_down(self):
        return self.down.isDown() or self._button_down_down

    def step_up(self, single_increment=False):
        if single_increment:
            self.val += self.increment*1.1
            return
        if self.log_increment:
            val = self.val
            res = val * self.log_factor() + np.sign(val)*self.increment/10. # to prevent rounding errors from
                                                                         # blocking the increment
            self.val = res#self.log_step**factor
        else:
            res = self.val + self.lin_delta() + self.increment/10.
            self.val = res

    def step_down(self, single_increment=False):
        if single_increment:
            self.val -= self.increment*1.1
            return
        if self.log_increment:
            val = self.val
            res = val / self.log_factor() - np.sign(val)*self.increment/10.  # to prevent rounding errors from
                                                                         # blocking the increment
            self.val = res #(self.log_step)**factor
        else:
            res = self.val - self.lin_delta() - self.increment/10.
            self.val = res

    def make_step_continuous(self):
        """

        :return:
        """
        APP.processEvents() # Ugly, but has to be there, otherwise, it could be that this function is called forever
        # because it takes the priority over released signal...
        if self.last_time is None:
            self.last_time = time.time()
        if self.is_sweeping_down() or self.is_sweeping_up():
            self.make_step()
            self.last_time = time.time()
            self.timer_arrow.setInterval(self.best_wait_time())
            self.timer_arrow.start()

    def make_step(self, single_increment=False):
        if self.is_sweeping_up():
            self.step_up(single_increment=single_increment)
        if self.is_sweeping_down():
            self.step_down(single_increment=single_increment)
        self.validate()

    def keyPressEvent(self, event):
        if not event.isAutoRepeat():
            if event.key()==QtCore.Qt.Key_Up:
                self._button_up_down = True
                self.first_increment()
            if event.key()==QtCore.Qt.Key_Down:
                self._button_down_down = True
                self.first_increment()
        return super(MyNumberSpinBox, self).keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            if event.key()==QtCore.Qt.Key_Up:
                self._button_up_down = False
                self.timer_arrow.stop()
            if event.key()==QtCore.Qt.Key_Down:
                self._button_down_down = False
                self.timer_arrow.stop()
        return super(MyNumberSpinBox, self).keyReleaseEvent(event)

    def validate(self):
        if self.line.isModified(): # otherwise don't trigger anything
            if self.val>self.max:
                self.val = self.max
            if self.val<self.min:
                self.val = self.min
            self.value_changed.emit()

    def set_per_second(self, val):
        self.per_second = val



class MyIntSpinBox(MyNumberSpinBox):
    def __init__(self, label, min=-2**13, max=2**13, increment=1,
                 log_increment=False, halflife_seconds=1.):
        super(MyIntSpinBox, self).__init__(label,
                                           min,
                                           max,
                                           increment,
                                           log_increment,
                                           halflife_seconds)

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
        return int(np.log10(self.max))


class MyFloatSpinBox(MyNumberSpinBox):
    def __init__(self, label, min=-1, max=1, increment=2.**(-13),
                 log_increment=False, halflife_seconds=2.0, decimals=4):
        self.decimals = decimals
        super(MyFloatSpinBox, self).__init__(label, min, max, increment, log_increment, halflife_seconds)
        width_in_characters = 6 + self.decimals
        self.setFixedWidth(width_in_characters*10)

    @property
    def val(self):
        if str(self.line.text())!=("%."+str(self.decimals) + "f")%self._val:
            return float(str(self.line.text()))
        return self._val # the value needs to be known to a precision better than the display to avoid deadlocks
                         # in increments

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

    def focusOutEvent(self, event):
        self.value_changed.emit()
        self.setStyleSheet("")

    def focusInEvent(self, event):
        self.value_changed.emit()
        self.setStyleSheet("MyFloatSpinBox{background-color:red;}")


class MyComplexSpinBox(QtGui.QFrame):
    """
    Two spinboxes representing a complex number, with the right keyboard shortcuts
    (up down for imag, left/right for real).
    """
    value_changed = QtCore.pyqtSignal()

    def __init__(self, label, min=-2**13, max=2**13, increment=1,
                 log_increment=False, halflife_seconds=1., decimals=4):
        super(MyComplexSpinBox, self).__init__()
        self.max = max
        self.min = min
        self.decimals = decimals
        self.increment = increment
        self.log_increment = log_increment
        self.halflife = halflife_seconds
        self.label = label
        self.lay = QtGui.QHBoxLayout()
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.real = MyFloatSpinBox(label=label,
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
        self.imag = MyFloatSpinBox(label=label,
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
        return super(MyComplexSpinBox, self).keyPressEvent(event)

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

        return super(MyComplexSpinBox, self).keyReleaseEvent(event)

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
        self.setStyleSheet("MyComplexSpinBox{background-color:red;}")

    @property
    def selected(self):
        return self.hasFocus()


class ListSpinBox(QtGui.QFrame):
    value_changed = QtCore.pyqtSignal()
    SpinBox = MyFloatSpinBox

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
        self.halflife = halflife_seconds
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
                            halflife_seconds=self.halflife,
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
    SpinBox = MyFloatSpinBox


class ListComplexSpinBox(ListSpinBox):
    SpinBox = MyComplexSpinBox


class BaseAttributeWidget(QtGui.QWidget):
    """
    Base class for Attribute Widgets. The class usually contains a label,
    and a widget, that is created by the function set_widget.
    """
    value_changed = QtCore.pyqtSignal()

    def __init__(self, name, module, widget_name=None):
        super(BaseAttributeWidget, self).__init__()
        self.setToolTip(getattr(module.__class__, name).__doc__)
        self.module = module
        self.name = name
        if widget_name is None:
            self.widget_name = self.name
        else:
            self.widget_name = widget_name
        self.acquisition_property = True  # property affects signal acquisition
        self.layout_v = QtGui.QVBoxLayout()
        self.label = QtGui.QLabel(self.widget_name)
        self.layout_v.addWidget(self.label, 0) # stretch=0
        self.layout_v.setContentsMargins(0, 0, 0, 0)
        self.set_widget()
        self.layout_v.addWidget(self.widget, 0) # stretch=0
        self.layout_v.addStretch(1)
        self.setLayout(self.layout_v)
        if self.module_value() is not None: # SelectAttributes without options might have a None value
            self.update_widget(self.module_value())

    def set_horizontal(self):
        self.layout_v.removeWidget(self.label)
        self.layout_v.removeWidget(self.widget)
        self.layout_h = QtGui.QHBoxLayout()
        self.layout_h.addWidget(self.label)
        self.layout_h.addWidget(self.widget)
        self.layout_v.addLayout(self.layout_h)

    def editing(self):
        """
        User is editing the property graphically don't mess up with him
        :return:
        """
        return False

    def update_widget(self, new_value):
        """
        Block QtSignals upon update to avoid infinite recursion.
        :return:
        """
        self.widget.blockSignals(True)
        self._update(new_value)
        self.widget.blockSignals(False)

    def set_widget(self):
        """
        To overwrite in base class.
        """
        self.widget = None

    def _update(self, new_value):
        """
        To overwrite in base class.
        """
        pass

    def module_value(self):
        """
        returns the module value, with the good type conversion.
        """
        return getattr(self.module, self.name)


class StringAttributeWidget(BaseAttributeWidget):
    """
    Property for string values.
    """
    def set_widget(self):
        """
        Sets up the widget (here a QSpinBox)
        :return:
        """

        self.widget = QtGui.QLineEdit()
        self.widget.setMaximumWidth(200)
        self.widget.textChanged.connect(self.write)

    def module_value(self):
        """
        returns the module value, with the good type conversion.

        :return: str
        """
        return str(self.module.__getattribute__(self.name))

    def write(self):
        setattr(self.module, self.name, str(self.widget.text()))
        self.value_changed.emit()

    def _update(self, new_value):
        """
        Updates the value displayed in the widget
        :return:
        """
        if not self.widget.hasFocus():
            self.widget.setText(new_value)


class TextAttributeWidget(StringAttributeWidget):
    """
    Property for multiline string values.
    """
    def set_widget(self):
        """
        Sets up the widget (here a QSpinBox)
        :return:
        """
        self.widget = QtGui.QTextEdit()
        self.widget.textChanged.connect(self.write)

    def write(self):
        setattr(self.module, self.name, str(self.widget.toPlainText()))
        self.value_changed.emit()


class NumberAttributeWidget(BaseAttributeWidget):
    """
    Base property for float and int.
    """
    def write(self):
        setattr(self.module, self.name, self.widget.value())
        self.value_changed.emit()

    def editing(self):
        return self.widget.line.hasFocus()

    def _update(self, new_value):
        """
        Updates the value displayed in the widget
        :return:
        """
        if not self.widget.hasFocus():
            self.widget.setValue(new_value)

    def set_increment(self, val):
        self.widget.setSingleStep(val)

    def set_maximum(self, val):
        self.widget.setMaximum(val)

    def set_minimum(self, val):
        self.widget.setMinimum(val)

    def set_per_second(self, val):
        self.widget.set_per_second(val)

    def set_log_increment(self):
        self.widget.set_log_increment()


class IntAttributeWidget(NumberAttributeWidget):
    """
    Property for integer values.
    """
    def set_widget(self):
        """
        Sets up the widget (here a QSpinBox)
        :return:
        """
        self.widget = MyIntSpinBox(None)#QtGui.QSpinBox()
        # self.widget.setMaximumWidth(200)
        self.widget.value_changed.connect(self.write)

    def module_value(self):
        """
        returns the module value, with the good type conversion.

        :return: int
        """
        return int(getattr(self.module, self.name))


class FloatAttributeWidget(NumberAttributeWidget):
    """
    Property for float values
    """
    def set_widget(self):
        """
        Sets up the widget (here a QDoubleSpinBox)
        :return:
        """
        self.widget = MyFloatSpinBox(None)#QtGui.QDoubleSpinBox()
        self.widget.value_changed.connect(self.write)

    def module_value(self):
        """
        returns the module value, with the good type conversion.

        :return: float
        """
        return float(getattr(self.module, self.name))


class ListAttributeWidget(BaseAttributeWidget):
    """
    The number of values is fixed (to 4 for now)

    This class is nearly identical with ListComplexAttributeWidget
    and the two should be merged together
    """
    ListSpinBox = ListFloatSpinBox
    listspinboxkwargs = dict(label=None,
                             min=-62.5e6,
                             max=62.5e6,
                             log_increment=True,
                             halflife_seconds=1.)

    def write(self):
        setattr(self.module, self.name, self.widget.get_list())
        self.value_changed.emit()

    def editing(self):
        return self.widget.editing()

    def _update(self, new_value):
        """
        Updates the value displayed in the widget
        :return:
        """
        if not self.widget.hasFocus():
            self.widget.set_list(new_value)

    def set_max_cols(self, num):
        """
        sets the max number of columns of the widget (after that, spin boxes are stacked under each other)
        """
        self.widget.set_max_cols(num)

    def set_increment(self, val):
        self.widget.set_increment(val)

    def set_maximum(self, val):
        self.widget.set_maximum(val)

    def set_minimum(self, val):
        self.widget.set_minimum(val)

    def set_widget(self):
        """
        Sets up the widget (here a ListFloatSpinBox)
        :return:
        """
        self.widget = self.ListSpinBox(**self.listspinboxkwargs)
        self.widget.value_changed.connect(self.write)

    def set_selected(self, index):
        """
        Selects the current active complex number.
        """
        self.widget.set_selected(index)

    def get_selected(self):
        """
        Get the selected number
        """
        return self.widget.get_selected()

    @property
    def number(self):
        return len(self.widget.spins)


class ListFloatAttributeWidget(ListAttributeWidget):
    ListSpinBox = ListFloatSpinBox
    listspinboxkwargs = dict(label=None,
                             min=-62.5e6,
                             max=62.5e6,
                             log_increment=True,
                             halflife_seconds=1.)


class ListComplexAttributeWidget(ListAttributeWidget):
    ListSpinBox = ListComplexSpinBox
    listspinboxkwargs = dict(label=None,
                             min=-62.5e6,
                             max=62.5e6,
                             log_increment=True,
                             halflife_seconds=1.)

# class ListComplexAttributeWidget(BaseAttributeWidget):
#     """
#     Attribute for arbitrary number of complex. New values can be added/removed with buttons
#     """
#     #def __init__(self, name, module, widget_name=None):
#     #    val = getattr(module, name)
#     #    super(ListComplexAttributeWidget, self).__init__(name, module,
#     #                                                     widget_name=widget_name)
#
#     def write(self):
#         setattr(self.module, self.name, self.widget.get_list())
#         self.value_changed.emit()
#
#     def editing(self):
#         return self.widget.editing()
#
#     def _update(self, new_value):
#         """
#         Updates the value displayed in the widget
#         :return:
#         """
#         if not self.widget.hasFocus():
#             self.widget.set_list(new_value)
#
#     def set_max_cols(self, num):
#         """
#         sets the max number of columns of the widget (after that, spin boxes are stacked under each other)
#         """
#         self.widget.set_max_cols(num)
#
#     def set_widget(self):
#         """
#         Sets up the widget (here a ListComplexSpinBox)
#         :return:
#         """
#
#         self.widget = ListComplexSpinBox(label=None,
#                                          min=-125e6/2,
#                                          max=125e6/2,
#                                          log_increment=True,
#                                          halflife_seconds=1.)
#         self.widget.value_changed.connect(self.write)
#
#     def set_selected(self, index):
#         """
#         Selects the current active complex number.
#         """
#         self.widget.set_selected(index)
#
#     def get_selected(self):
#         """
#         Get the selected number
#         """
#         return self.widget.get_selected()
#
#     @property
#     def number(self):
#         return len(self.widget.spins)


class ListComboBox(QtGui.QWidget):
    value_changed = QtCore.pyqtSignal()

    def __init__(self, number, name, options):
        super(ListComboBox, self).__init__()
        self.setToolTip("First order filter frequencies \n"
                        "negative values are for high-pass \n"
                        "positive for low pass")
        self.lay = QtGui.QHBoxLayout()
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.combos = []
        self.options = options
        for i in range(number):
            combo = QtGui.QComboBox()
            self.combos.append(combo)
            combo.addItems(self.options)
            combo.currentIndexChanged.connect(self.value_changed)
            self.lay.addWidget(combo)
        self.setLayout(self.lay)

    def get_list(self):
        return [float(combo.currentText()) for combo in self.combos]

    def set_max_cols(self, n_cols):
        """
        If more than n boxes are required, go to next line
        """
        if len(self.combos)<=n_cols:
            return
        for item in self.combos:
            self.lay.removeWidget(item)
        self.v_layouts = []
        n = len(self.combos)
        n_rows = int(np.ceil(n*1.0/n_cols))
        j = 0
        for i in range(n_cols):
            layout = QtGui.QVBoxLayout()
            self.lay.addLayout(layout)
            for j in range(n_rows):
                index = i*n_rows + j
                if index>=n:
                    break
                layout.addWidget(self.combos[index])

    def set_list(self, val):
        if not np.iterable(val):
            val = [val]
        for i, v in enumerate(val):
            v = str(int(v))
            index = self.options.index(v)
            self.combos[i].setCurrentIndex(index)


class FilterAttributeWidget(BaseAttributeWidget):
    """
    Property for list of floats (to be choosen in a list of valid_frequencies)
    The attribute descriptor needs to expose a function valid_frequencies(module)
    """
    def __init__(self, name, module, widget_name=None):
        val = getattr(module, name)
        if np.iterable(val):
            self.number = len(val)
        else:
            self.number = 1
        #self.defaults = name + 's'
        self.options = getattr(module.__class__, name).valid_frequencies(module)
        super(FilterAttributeWidget, self).__init__(name, module,
                                                    widget_name=widget_name)

    def set_widget(self):
        """
        Sets up the widget (here a QDoubleSpinBox)
        :return:
        """
        self.widget = ListComboBox(self.number, "", list(map(str, self.options)))
        self.widget.value_changed.connect(self.write)

    def write(self):
        """
        Sets the module property value from the current gui value

        :return:
        """

        setattr(self.module, self.name, self.widget.get_list())
        if self.acquisition_property:
            self.value_changed.emit()

    def _update(self, new_value):
        """
        Sets the gui value from the current module value

        :return:
        """

        #val = getattr(self.module, self.name)

        if isinstance(new_value, str) or not np.iterable(new_value): # only 1
            # element in the FilterAttribute, make a list for consistency,
            # used to be basestring
            val = [new_value]
        self.widget.set_list(new_value)

    def set_max_cols(self, n_cols):
        self.widget.set_max_cols(n_cols)


class SelectAttributeWidget(BaseAttributeWidget):
    """
    Multiple choice property.
    """
    def __init__(self, name, module, widget_name=None, **kwargs):
        return super(SelectAttributeWidget, self).__init__(name, module,
                                                           widget_name=widget_name,
                                                           **kwargs)

    def set_widget(self):
        """
        Sets up the widget (here a QComboBox)

        :return:
        """
        self.widget = QtGui.QComboBox()
        self.widget.addItems(self.options)
        self.widget.currentIndexChanged.connect(self.write)

    @property
    def options(self):
        """
        All possible options (as found in module.prop_name + 's')

        :return:
        """
        # return self.defaults  # getattr(self.module, self.defaults)
        opt = recursive_getattr(self.module, '__class__.' + self.name + '.options')(self.module)
        opt = [str(v) for v in opt]
        if len(opt) == 0:
            opt = [""]
        return opt

    def write(self):
        """
        Sets the module property value from the current gui value

        :return:
        """
        try:
            setattr(self.module, self.name, str(self.widget.currentText()))
        except ValueError as e1:
            # typically string - int - conversion related
            options = getattr(self.module.__class__, self.name).options(self.module).keys()
            try:
                index = [str(k) for k in options].index(str(self.widget.currentText()))
            except ValueError as e2:
                raise e1
            else:
                setattr(self.module, self.name, options[index])
        self.value_changed.emit()

    def _update(self, new_value):
        """
        Sets the gui value from the current module value
        """
        try:
            index = self.options.index(str(new_value))
        except (IndexError, ValueError):
            self.module._logger.warning("SelectWidget %s could not find current value %s "
                                        "in the options %s",
                                        self.name, new_value, self.options)
            index = 0
        self.widget.setCurrentIndex(index)

    def change_options(self, new_options):
        """
        The options of the combobox can be changed dynamically. new_options is
        a list of strings.
        """
        self.widget.blockSignals(True)
        #self.defaults = new_options
        self.widget.clear()
        #self.widget.addItems(new_options)
        # do not trust the new options, rather call options again
        self.widget.addItems(self.options)
        try:
            self._update(new_value=self.module_value())
        except ValueError:
            pass
        self.widget.blockSignals(False)


class PhaseAttributeWidget(FloatAttributeWidget):
    pass


class FrequencyAttributeWidget(FloatAttributeWidget):
    def __init__(self, name, module, widget_name=None):
        super(FrequencyAttributeWidget, self).__init__(name, module,
                                                       widget_name=widget_name)
        self.set_per_second(10)


class LedAttributeWidget(BaseAttributeWidget):
    """ Boolean property with a button whose text and color indicates whether """
    def set_widget(self):
        desc = recursive_getattr(self.module, '__class__.'+self.name)
        val = recursive_getattr(self.module, self.name)
        self.widget = QtGui.QPushButton("setting up...")
        self.widget.clicked.connect(self.button_clicked)

    def button_clicked(self):
        val = getattr(self.module, self.name)
        # override module state with current button state
        # if self.widget.text() =='start':
        #     val = False
        # else:
        #     val = True
        setattr(self.module, self.name, not val)

    def _update(self, new_value):
        if new_value == True:
            color = 'green'
            text = 'stop'
        else:
            color = 'red'
            text = 'start'
        self.widget.setStyleSheet("background-color:%s"%color)
        self.widget.setText(text)


class BoolAttributeWidget(BaseAttributeWidget):
    """
    Boolean property
    """
    def set_widget(self):
        """
        Sets the widget (here a QCheckbox)

        :return:
        """
        self.widget = QtGui.QCheckBox()
        self.widget.stateChanged.connect(self.write)

    def write(self):
        """
        Sets the module value from the current gui value

        :return:
        """
        setattr(self.module, self.name, self.widget.checkState() == 2)
        if self.acquisition_property:
            self.value_changed.emit()

    def _update(self, new_value):
        """
        Sets the gui value from the current module value

        :return:
        """
        self.widget.setCheckState(new_value * 2)


class BoolIgnoreAttributeWidget(BoolAttributeWidget):
    """
    Boolean property with additional option 'ignore' that is shown
    as a grey check in GUI
    """
    _gui_to_attribute_mapping = Bijection({0: False,
                                           1: 'ignore',
                                           2: True})

    def set_widget(self):
        """
        Sets the widget (here a QCheckbox)
        :return:
        """
        self.widget = QtGui.QCheckBox()
        self.widget.setTristate(True)
        self.widget.stateChanged.connect(self.write)
        self.setToolTip("Checked:\t    on\nUnchecked: off\nGrey:\t    ignore")

    def write(self):
        """
        Sets the module value from the current gui value
        :return:
        """
        setattr(self.module, self.name, self._gui_to_attribute_mapping[self.widget.checkState()])
        if self.acquisition_property:
            self.value_changed.emit()

    def _update(self, new_value):
        """
        Sets the gui value from the current module value
        :return:
        """
        self.widget.setCheckState(self._gui_to_attribute_mapping.inverse[new_value])


class CurveAttributeWidget(BaseAttributeWidget):
    """
    Base property for float and int.
    """
    def set_widget(self):
        """
        Sets the widget (here a QCheckbox)
        :return:
        """
        self.widget = pg.GraphicsWindow(title="Curve")
        self.plot_item = self.widget.addPlot(title="Curve")
        self.plot_item_phase = self.widget.addPlot(row=1, col=0,
                                                   title="Phase (deg)")
        self.plot_item_phase.setXLink(self.plot_item)
        self.plot_item.showGrid(y=True, alpha=1.)
        self.plot_item_phase.showGrid(y=True, alpha=1.)

        self.curve = self.plot_item.plot(pen='g')
        self.curve_phase = self.plot_item_phase.plot(pen='g')

        #self.setToolTip("Checked:\t    on\nUnchecked: off\nGrey:\t    ignore")

    def write(self):
        # nothing to write from a curve
        pass
        #setattr(self.module, self.name, self.widget.value())
        #self.value_changed.emit()

    def _update(self, new_value):
        """
        Updates the value displayed in the widget
        :return:
        """
        if new_value is None:
            return
        try:
            data = getattr(self.module, '_' + self.name + '_object').data
            name = getattr(self.module, '_' + self.name + '_object').params['name']
        except:
            pass
        else:
            x = data.index.values
            y = data.values
            if not np.isreal(y).all():
                self.curve.setData(x, self._magnitude(y))
                self.curve_phase.setData(x, self._phase(y))
                self.plot_item_phase.show()
                self.plot_item.setTitle(name + " - Magnitude (dB)")
            else:
                self.curve.setData(x, np.real(y))
                self.plot_item_phase.hide()
                self.plot_item.setTitle(name)


    def _magnitude(self, data):
        return 20. * np.log10(np.abs(data) + sys.float_info.epsilon)

    def _phase(self, data):
        return np.angle(data, deg=True)


class CurveSelectAttributeWidget(SelectAttributeWidget):
    """
    Select one or many curves.
    """
    def set_widget(self):
        """
        Sets up the widget (here a QComboBox)

        :return:
        """
        self.widget = QtGui.QListWidget()
        self.widget.addItems(self.options)
        self.widget.currentItemChanged.connect(self.write)

    def write(self):
        """
        Sets the module property value from the current gui value
        :return:
        """
        try:
            setattr(self.module, self.name, int(self.widget.currentItem().text()))
        except:
            pass
        else:
            self.value_changed.emit()

    def _update(self, new_value):
        """
        Sets the gui value from the current module value
        """
        if new_value is None:
            new_value = -1
        if hasattr(new_value, 'pk'):
            new_value = new_value.pk
        try:
            index = self.options.index(str(new_value))
        except IndexError:
            self.module._logger.warning("SelectWidget %s could not find "
                                        "current value %s in the options %s",
                                        self.name, self.new_value, self.options)
            index = 0
        self.widget.setCurrentRow(index)
