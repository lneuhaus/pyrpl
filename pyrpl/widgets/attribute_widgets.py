"""
AttributeWidgets' hierarchy is parallel to Attribute' hierarchy
An instance attr of Attribute can create its AttributeWidget counterPart by calling attr.create_widget(name, parent)
"""

from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import time
import functools

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
        string+="Press up/down or mouse wheel to tune."
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
        if self.val>self.max:
            self.val = self.max
        if self.val<self.min:
            self.val = self.min
        self.value_changed.emit()

    def set_per_second(self, val):
        self.per_second = val


class MyDoubleSpinBox(MyNumberSpinBox):
    def __init__(self, label, min=-1, max=1, increment=2.**(-13),
                 log_increment=False, halflife_seconds=2.0, decimals=4):
        self.decimals = decimals
        super(MyDoubleSpinBox, self).__init__(label, min, max, increment, log_increment, halflife_seconds)

    @property
    def val(self):
        if str(self.line.text())!=("%."+str(self.decimals) + "f")%self._val:
            return float(str(self.line.text()))
        return self._val # the value needs to be known to a precision better than the display to avoid deadlocks
                         # in increments

    @val.setter
    def val(self, new_val):
        self._val = new_val # in case the line is not updated immediately
        self.line.setText(("%."+str(self.decimals) + "f")%new_val)
        self.value_changed.emit()
        return new_val

    def max_num_letter(self):
        """
        Returns the maximum number of letters
        """
        return self.decimals + int(np.log10(self.max))



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
        #if self.line.text()!=("%.i")%self._val:
            return int(str(self.line.text()))
        #return self._val

    @val.setter
    def val(self, new_val):
        #self._val = new_val
        self.line.setText(("%.i")%new_val)
        self.value_changed.emit()
        return new_val

    def max_num_letter(self):
        """
        Maximum number of letters in line
        """
        return int(np.log10(self.max))


class BaseAttributeWidget(QtGui.QWidget):
    """
    Base class for Attribute Widgets. The class usually contains a label,
    and a widget, that is created by the function set_widget.
    """
    value_changed = QtCore.pyqtSignal()

    def __init__(self, name, module):
        super(BaseAttributeWidget, self).__init__()
        self.setToolTip(getattr(module.__class__, name).__doc__)
        self.module = module
        self.name = name
        self.acquisition_property = True  # property affects signal acquisition
        self.layout_v = QtGui.QVBoxLayout()
        self.label = QtGui.QLabel(name)
        self.layout_v.addWidget(self.label, 0) # stretch=0
        self.layout_v.setContentsMargins(0, 0, 0, 0)
        #self.module = self.module_widget.module
        self.set_widget()
        self.layout_v.addWidget(self.widget, 0) # stretch=0
        self.layout_v.addStretch(1)
        self.setLayout(self.layout_v)
        if self.module_value() is not None: # SelectAttributes without options might have a None value
            self.update_widget(self.module_value())
        #self.module_widget.register_layout.addLayout(self.layout_v)
        #self.value_changed.connect(self.emit_widget_value_changed)
        #self.module_widget.property_watch_timer.timeout. \
        #    connect(self.update_widget)

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

    #def emit_widget_value_changed(self):
    #    if self.acquisition_property:
    #        self.module_widget.property_changed.emit()

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

    def _update(self):
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

        self.widget = MyDoubleSpinBox(None)#QtGui.QDoubleSpinBox()
        self.widget.value_changed.connect(self.write)

    def module_value(self):
        """
        returns the module value, with the good type conversion.

        :return: float
        """

        return float(getattr(self.module, self.name))

class MyComplexSpinBox(QtGui.QFrame):
    """
    Two spinboxes representing a complex number, with the right keyboard shortcuts
    (up down for imag, left/right for real).
    """
    value_changed = QtCore.pyqtSignal()

    def __init__(self, label, min=-2**13, max=2**13, increment=1,
                 log_increment=False, halflife_seconds=1., decimals=0):
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
        self.real = MyDoubleSpinBox(label=label,
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
        self.imag = MyDoubleSpinBox(label=label,
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
        #if self.line.text()!=("%.i")%self._val:
            return self.real.val + 1j*self.imag.val
        #return self._val

    @val.setter
    def val(self, new_val):
        #self._val = new_val
        self.real.val = np.real(new_val)
        self.imag.val = np.imag(new_val)
        return new_val

    def max_num_letter(self):
        """
        Maximum number of letters in line
        """
        return int(np.log10(self.max))

    def focusOutEvent(self, event):
        self.value_changed.emit()
        self.setStyleSheet("")

    def focusInEvent(self, event):
        self.value_changed.emit()
        self.setStyleSheet("MyComplexSpinBox{background-color:red;}")

    @property
    def selected(self):
        return self.hasFocus()


class ListFloatSpinBox(QtGui.QWidget):
    """
    No add or remove buttons yet (mainly used to represent analog filters)
    """
    value_changed = QtCore.pyqtSignal()

    def __init__(self, label, n_spins=4, min=-65e6, max=65e6, increment=1., log_increment=True, halflife_seconds=1.):
        super(ListFloatSpinBox, self).__init__()
        self.label = label
        self.min = min
        self.max = max
        self.increment = increment
        self.halflife = halflife_seconds
        self.log_increment = log_increment
        self.increment = increment
        self.lay = QtGui.QVBoxLayout(self)
        self.lay_hs = [QtGui.QHBoxLayout()]
        self.lay.addLayout(self.lay_hs[0])
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.spins = []
        for index in range(n_spins):
            spin = MyDoubleSpinBox(label=None,
                                   min=min,
                                   max=max,
                                   increment=increment,
                                   log_increment=log_increment,
                                   halflife_seconds=halflife_seconds)
            spin.value_changed.connect(self.value_changed)
            self.spins.append(spin)
            self.lay_hs[0].addWidget(spin)

        if label is not None:
            self.label = QtGui.QLabel(self.label)
            self.lay.addWidget(self.label)
            self.setLayout(self.lay)

    def get_list(self):
        return [spin.val for spin in self.spins]

    def set_list(self, list_val):
        for index, val in enumerate(list_val):
            self.spins[index].val = val

        for i in range(index, len(self.spins)):
            self.spins[i].val = 0

    def remove_all_spins_from_layout(self):
        widget = 1
        while widget is not None:
            widget = self.lay_hs[0].takeAt(0)

    def set_max_cols(self, n):
        index_col = 0
        self.remove_all_spins_from_layout()
        current_layout = self.lay_hs[0]
        for spin in self.spins:
            current_layout.addWidget(spin)
            index_col+=1
            if index_col>=n:
                index_col = 0
                current_layout = QtGui.QHBoxLayout()
                self.lay_hs.append(current_layout)
                self.lay.addLayout(current_layout)



class ListComplexSpinBox(QtGui.QFrame):
    value_changed = QtCore.pyqtSignal()

    def __init__(self, label, min=-65e6, max=65e6, increment=1., log_increment=True, halflife_seconds=1.):
        super(ListComplexSpinBox, self).__init__()
        self.label = label
        self.min = min
        self.max = max
        self.increment = increment
        self.halflife = halflife_seconds
        self.log_increment = log_increment
        self.incement = increment
        self.lay = QtGui.QVBoxLayout()
        self.spins = []
        self.button_removes = []
        self.spin_lays = []
        self.halflife = halflife_seconds
        if label is not None:
            self.label = QtGui.QLabel(self.name)
            self.lay.addWidget(self.label)
        #for i in range(number):
        #    self.add_spin()
        self.button_add = QtGui.QPushButton("+")
        self.button_add.clicked.connect(self.add_spin_and_select)

        self.lay.addWidget(self.button_add)
        self.lay.addStretch(1)
        self.lay.setContentsMargins(0,0,0,0)
        self.setLayout(self.lay)
        self.selected = None

    def add_spin_and_select(self):
        self.add_spin()
        self.spins[-1].val = -1e4 -1j*1e3
        self.set_selected(-1)

    def add_spin(self):
        index = len(self.spins)
        spin = MyComplexSpinBox(label="",
                                min=self.min,
                                max=self.max,
                                increment=self.increment,
                                log_increment=self.log_increment,
                                halflife_seconds=self.halflife,
                                decimals=0)
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

class ListFloatAttributeWidget(BaseAttributeWidget):
    """
    The number of values is fixed (to 4 for now)
    """
    def set_widget(self):
        """
        Sets up the widget (here a ListFloatSpinBox)
        :return:
        """

        self.widget = ListFloatSpinBox(label=None,
                                         min=-65e6,
                                         max=65e6,
                                         log_increment=True,
                                         halflife_seconds=1.)
        self.widget.value_changed.connect(self.write)

    def write(self):
        setattr(self.module, self.name, self.widget.get_list())
        self.value_changed.emit()

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


class ListComplexAttributeWidget(BaseAttributeWidget):
    """
    Attribute for arbitrary number of complex. New values can be added/removed with buttons
    """
    def __init__(self, name, module):
        val = getattr(module, name)
        #self.defaults = name + 's'
        super(ListComplexAttributeWidget, self).__init__(name, module)

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

    def set_widget(self):
        """
        Sets up the widget (here a ListComplexSpinBox)
        :return:
        """

        self.widget = ListComplexSpinBox(label=None,
                                         min=-65e6,
                                         max=65e6,
                                         log_increment=True,
                                         halflife_seconds=1.)
        #self.widget.setDecimals(4)
        #self.widget.setSingleStep(0.01)
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
    """
    @property
    def options(self):
        return  self._options
    """

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

    def __init__(self, name, module):
        val = getattr(module, name)
        if np.iterable(val):
            self.number = len(val)
        else:
            self.number = 1
        #self.defaults = name + 's'
        self.options = getattr(module.__class__, name).valid_frequencies(module)
        super(FilterAttributeWidget, self).__init__(name, module)

    def set_widget(self):
        """
        Sets up the widget (here a QDoubleSpinBox)
        :return:
        """

        self.widget = ListComboBox(self.number, "", list(map(str, self.options)))#QtGui.QDoubleSpinBox()
        #self.widget.setDecimals(4)
        #self.widget.setSingleStep(0.01)
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

        if isinstance(new_value, basestring) or not np.iterable(new_value): # only 1 element in the FilterAttribute, make a list for consistency
            val = [new_value]
        self.widget.set_list(new_value)

    def set_max_cols(self, n_cols):
        self.widget.set_max_cols(n_cols)

class SelectAttributeWidget(BaseAttributeWidget):
    """
    Multiple choice property.
    """

    def __init__(self, name, module, defaults=None):
        if defaults is not None:
            self.defaults = defaults
        else:
            self.defaults = name + 's'
        super(SelectAttributeWidget, self).__init__(name, module)

    def set_widget(self):
        """
        Sets up the widget (here a QComboBox)

        :return:
        """

        self.widget = QtGui.QComboBox()
        self.widget.addItems(list(map(str, self.options)))
        self.widget.currentIndexChanged.connect(self.write)

    @property
    def options(self):
        """
        All possible options (as found in module.prop_name + 's')

        :return:
        """
        return self.defaults #getattr(self.module, self.defaults)

    def write(self):
        """
        Sets the module property value from the current gui value

        :return:
        """
        setattr(self.module, self.name, str(self.widget.currentText()))
        #if self.acquisition_property:
        self.value_changed.emit()

    def _update(self, new_value):
        """
        Sets the gui value from the current module value
        """
        if len(getattr(self.module.__class__, self.name).options(self.module))==0: # None is OK if no options are available
            if new_value is None:
                return
        index = list(self.options).index(new_value)
        self.widget.setCurrentIndex(index)

    def change_options(self, new_options):
        """
        The options of the combobox can be cahnged dynamically. new_options is a list of strings.
        """
        self.widget.blockSignals(True)
        self.defaults = new_options
        self.widget.clear()
        self.widget.addItems(new_options)
        try:
            self._update(new_value=self.module_value())
        except ValueError:
            pass
        self.widget.blockSignals(False)


class MyListStageOutputAttributeWidget(QtGui.QWidget):
    value_changed = QtCore.pyqtSignal()
    def __init__(self, parent=None):
        super(MyListStageOutputAttributeWidget, self).__init__(parent)
        self.layout = QtGui.QHBoxLayout(self)
        self.layout1 = QtGui.QVBoxLayout()
        self.layout2 = QtGui.QVBoxLayout()
        self.layout3 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.layout1)
        self.layout.addLayout(self.layout2)
        self.layout.addLayout(self.layout3)

        self.output_on = []
        self.offset_enabled = []
        self.offset = []

    def set_dict(self, dic):
        self.remove_lines()
        index = 0
        for key, val in dic.items():
            if index<len(self.output_on):
                self.set_line_name_value(index, key, val)
                index += 1
            else:
                self.add_line(key, val)
                index +=1
        while(True):
            try:
                self.remove_line(index)
            except IndexError:
                break

    def get_dict(self):
        dic = dict()
        for on, offset_enabled, offset in zip(self.output_on, self.offset_enabled, self.offset):
            dic[str(on.text())] = (on.checkState()==2, offset_enabled.checkState()==2, offset.val)
        return dic

    def add_line(self, name, val):
        (is_on, offset_enabled, offset) = val

        on = QtGui.QCheckBox(name, self)
        self.output_on.append(on)
        on.setChecked(is_on)
        on.stateChanged.connect(self.value_changed)
        self.layout1.addWidget(on)

        oe = QtGui.QCheckBox(self)
        oe.setChecked(offset_enabled)
        oe.stateChanged.connect(self.value_changed)
        self.layout2.addWidget(oe)
        self.offset_enabled.append(oe)

        offs = MyDoubleSpinBox("")
        offs.val = offset
        offs.value_changed.connect(self.value_changed)
        self.layout3.addWidget(offs)
        self.offset.append(offs)

    def set_line_name_value(self, index, name, val):
        (is_on, offset_enabled, offset) = val
        self.output_on[index].setText(name)
        self.output_on[index].setChecked(is_on)
        self.offset_enabled_on[index].setChecked(offset_enabled)
        self.offset[index].val = offset

    def get_line_value(self, index):
        on = self.output_on[index].chekState()==2
        offset_enabled = self.offset_enabled[index].checkState()==2
        offset = self.offset[index].val
        return (on, offset_enabled, offset)

    def remove_line(self, index):
        output_on = self.output_on.pop(index)
        offset_on = self.offset_enabled.pop(index)
        offset = self.offset.pop(index)
        output_on.deleteLater()
        offset_on.deleteLater()
        offset.deleteLater()

    def remove_lines(self):
        while True:
            try:
                self.remove_line(0)
            except IndexError:
                break

class ListStageOutputAttributeWidget(BaseAttributeWidget):
    def set_widget(self):
        """
        Sets up the widget (here a MyListStageOutputAttributeWidget)
        """
        self.layout_v.setSpacing(0)
        self.widget = MyListStageOutputAttributeWidget()
        self.widget.value_changed.connect(self.write)
        self.layout_col_names = QtGui.QHBoxLayout()
        self.layout_v.insertLayout(0, self.layout_col_names)
        self.layout_v.removeWidget(self.label)
        self.label.deleteLater()
        self.label_on = QtGui.QLabel("output_on")
        self.layout_col_names.addWidget(self.label_on)
        self.label_offset = QtGui.QLabel("start_offset")
        self.layout_col_names.addWidget(self.label_offset)

    def write(self):
        """
        Sets the module property value from the current gui value
        """
        setattr(self.module, self.name, self.widget.get_dict())
        #if self.acquisition_property:
        self.value_changed.emit()

    def _update(self, new_value):
        """
        Sets the gui value from the current module value
        """
        self.widget.set_dict(new_value)

#class DynamicSelectAttributeWidget(SelectAttributeWidget):
#    """
#    Multiple choice property, with optiosn evaluated at run-time:
#    the options in the combobox have to be filled upon click.
#    """
#    def __init__(self, name, module):
#        BaseAttributeWidget.__init__(self, name, module) # don' t do the SelectAttributeWidget initialization.
#
#    def set_widget(self):
#        """
#        Sets up the widget (here a QComboBox).
#        """
#        self.widget = QtGui.QComboBox()
#        self.widget.currentIndexChanged.connect(self.write)
#
#    @property
#    def options(self):
#        """
#        All possible options.
#        """
#        return getattr(self.module.__class__, self.name).options(self.module)
#
#    def


class PhaseAttributeWidget(FloatAttributeWidget):
    pass


class FrequencyAttributeWidget(FloatAttributeWidget):
    def __init__(self, name, module):
        super(FrequencyAttributeWidget, self).__init__(name, module)
        self.set_per_second(10)


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
