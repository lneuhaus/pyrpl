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
                 log_increment=False, halflife_seconds=1.):
        """
        :param label: label of the button
        :param min: min value
        :param max: max value
        :param increment: increment of the underlying register
        :param log_increment: boolean: when buttons up/down are pressed, should the value change linearly or log
        :param halflife_seconds: when button is in log, how long to change the value by a factor 2.
        """
        super(MyNumberSpinBox, self).__init__(None)
        self.min = min
        self.max = max
        self.increment = increment
        self.update_tooltip()
        self._val = 0
        self.halflife_seconds = halflife_seconds
        self.log_increment = log_increment

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
            func()

    def first_increment(self):
        """
        Once +/- pressed for timer_initial_latency ms, start to update continuously
        """

        if self.log_increment:
            self.last_time = time.time() # don't make a step, but store present time
            self.timer_arrow.start()
        else:
            self.make_step()
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
        dt = self.timer_arrow.interval()  # time since last step
        return 2**(dt*0.001/self.halflife_seconds)

    def best_wait_time(self):
        """
        Time to wait until value should reach the next increment
        If this time is shorter than self.timer_min_interval, then, returns timer_min_interval
        :return:
        """
        if self.log_increment:
            val = self.val
            if self.is_sweeping_up():
                next_val = val + np.sign(val)*self.increment
                factor = next_val*1./val
            if self.is_sweeping_down():
                next_val = val - np.sign(val)*self.increment
                factor = val*1.0/next_val
            return int(np.ceil(max(self.timer_min_interval, 1000*np.log2(factor))))
        else:
            return self.timer_min_interval

    def is_sweeping_up(self):
        return self.up.isDown() or self._button_up_down

    def is_sweeping_down(self):
        return self.down.isDown() or self._button_down_down

    def step_up(self, factor=1):
        if self.log_increment:
            val = self.val
            res = val * self.log_factor() + np.sign(val)*self.increment/10. # to prevent rounding errors from
                                                                         # blocking the increment
            self.val = res#self.log_step**factor
        else:
            res = self.val + self.increment*factor + self.increment/10.
            self.val = res

    def step_down(self, factor=1):
        if self.log_increment:
            val = self.val
            res =  val / self.log_factor() - np.sign(val)*self.increment/10.  # to prevent rounding errors from
                                                                         # blocking the increment
            self.val = res #(self.log_step)**factor
        else:
            res = self.val - self.increment*factor - self.increment/10.
            self.val = res

    def make_step_continuous(self):
        """

        :return:
        """
        APP.processEvents() # Ugly, but has to be there, otherwise, it could be that this function is called forever
        # because it takes the priority over released signal...
        if self.is_sweeping_down() or self.is_sweeping_up():
            self.make_step()
            self.timer_arrow.setInterval(self.best_wait_time())
            self.timer_arrow.start()

    def make_step(self):
        if self.is_sweeping_up():
            self.step_up()
        if self.is_sweeping_down():
            self.step_down()
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


class MyDoubleSpinBox(MyNumberSpinBox):
    def __init__(self, label, min=-1, max=1, increment=2.**(-13),
                 log_increment=False, halflife_seconds=1.0, decimals=3):
        self.decimals = decimals
        super(MyDoubleSpinBox, self).__init__(label, min, max, increment, log_increment, halflife_seconds)

    @property
    def val(self):
        if self.line.text()!=("%."+str(self.decimals) + "f")%self._val:
            return float(self.line.text())
        return self._val # the value needs to be known to a precision better than the display to avoid deadlocks
                         # in increments

    @val.setter
    def val(self, new_val):
        self._val = new_val # in case the line is not updated immediately
        self.line.setText(("%."+str(self.decimals) + "f")%new_val)
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
            return int(self.line.text())
        #return self._val

    @val.setter
    def val(self, new_val):
        #self._val = new_val
        self.line.setText(("%.i")%new_val)
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
        self.update()

        #self.module_widget.register_layout.addLayout(self.layout_v)
        #self.value_changed.connect(self.emit_widget_value_changed)
        #self.module_widget.property_watch_timer.timeout. \
        #    connect(self.update_widget)

    def editing(self):
        """
        User is editing the property graphically don't mess up with him
        :return:
        """

        return False

    #def emit_widget_value_changed(self):
    #    if self.acquisition_property:
    #        self.module_widget.property_changed.emit()

    def update_widget(self):
        """
        Block QtSignals upon update to avoid infinite recursion.
        :return:
        """

        self.widget.blockSignals(True)
        self.update()
        self.widget.blockSignals(False)

    def set_widget(self):
        """
        To overwrite in base class.
        """

        self.widget = None

    def update(self):
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


    def update(self):
        """
        Updates the value displayed in the widget
        :return:
        """
        if not self.widget.hasFocus():
            self.widget.setText(self.module_value())


class NumberAttributeWidget(BaseAttributeWidget):
    """
    Base property for float and int.
    """

    def write(self):
        setattr(self.module, self.name, self.widget.value())
        self.value_changed.emit()

    def editing(self):
        return self.widget.line.hasFocus()

    def update(self):
        """
        Updates the value displayed in the widget
        :return:
        """
        if not self.widget.hasFocus():
            self.widget.setValue(self.module_value())

    def set_increment(self, val):
        self.widget.setSingleStep(val)

    def set_maximum(self, val):
        self.widget.setMaximum(val)

    def set_minimum(self, val):
        self.widget.setMinimum(val)


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
        self.widget.setMaximumWidth(200)
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


class ListComplexSpinBox(QtGui.QWidget):
    value_changed = QtCore.pyqtSignal()

    def __init__(self, number, label, min=-1., max=1., increment=0., log_increment=True, halflife_seconds=1.):
        super(ListComplexSpinBox, self).__init__()
        self.label = label
        self.min = min
        self.max = max
        self.increment = increment
        self.halflife = halflife_seconds
        self.log_increment = log_increment
        self.incement = increment
        self.lay = QtGui.QVBoxLayout()
        self.spins_real = []
        self.spins_imag = []
        self.button_removes = []
        self.spin_lays = []
        self.halflife = halflife_seconds
        if label is not None:
            self.label = QtGui.QLabel(self.name)
            self.lay.addWidget(self.label)
        for i in range(number):
            self.add_spin()
        self.button_add = QtGui.QPushButton("+")
        self.button_add.clicked.connect(self.add_spin)
        self.button_remove = QtGui.QPushButton("-")

        self.lay.addWidget(self.button_add)
        self.setLayout(self.lay)

    def add_spin(self):
        index = len(self.spins_real)
        spin_real = MyDoubleSpinBox(label="",
                                    min=self.min,
                                    max=self.max,
                                    increment=self.increment,
                                    log_increment=self.log_increment,
                                    halflife_seconds=self.halflife,
                                    decimals=0)
        spin_imag = MyDoubleSpinBox(label="",
                                    min=self.min,
                                    max=self.max,
                                    increment=self.increment,
                                    log_increment=self.log_increment,
                                    halflife_seconds=self.halflife,
                                    decimals=0)
        self.spins_real.append(spin_real)
        self.spins_imag.append(spin_imag)
        spin_lay = QtGui.QHBoxLayout()
        self.spin_lays.append(spin_lay)
        spin_lay.addWidget(spin_real)
        spin_lay.addWidget(spin_imag)
        button_remove = QtGui.QPushButton('-')
        self.button_removes.append(button_remove)
        spin_lay.addWidget(button_remove)
        spin_real.value_changed.connect(self.value_changed)
        spin_imag.value_changed.connect(self.value_changed)
        button_remove.clicked.connect(functools.partial(self.remove_spin, button=button_remove))
        self.lay.insertLayout(index + 1*(self.label is not None), spin_lay) #QLabel occupies the first row

    def remove_spin(self, button):
        index = self.button_removes.index(button)

        button = self.button_removes.pop(index)
        spin_real = self.spins_real.pop(index)
        spin_imag = self.spins_imag.pop(index)
        spin_lay = self.spin_lays.pop(index)

        self.lay.removeItem(spin_lay)

        spin_real.deleteLater()
        spin_imag.deleteLater()
        button.deleteLater()
        spin_lay.deleteLater()

    def get_list(self):
        return [spin_real.value() + 1j*spin_imag.value() for \
                (spin_real, spin_imag) in zip(self.spins_real, self.spins_imag)]

    def set_list(self, list_val):
        for index, val in enumerate(list_val):
            if index>=len(self.spins_real):
                self.add_spin()
            self.spins_real[index].val = np.real(val)
            self.spins_imag[index].val = np.imag(val)

        to_delete = []
        for other_index in range(len(list_val), len(self.spins_real)):
            to_delete.append(self.button_removes[other_index]) # don't loop on a list that is
                                                                                 # shrinking !
        for button in to_delete:
            self.remove_spin(button)

    def editing(self):
        edit = False
        for spin in self.spins:
            edit = edit or spin.editing()
        return edit()



class ListComplexAttributeWidget(BaseAttributeWidget):
    """
    Attribute for arbitrary number for floats
    """
    def __init__(self, name, module):
        val = getattr(module, name)
        if np.iterable(val):
            self.number = len(val)
        else:
            self.number = 1
        #self.defaults = name + 's'
        super(ListComplexAttributeWidget, self).__init__(name, module)

    def write(self):
        setattr(self.module, self.name, self.widget.get_list())
        self.value_changed.emit()

    def editing(self):
        return self.widget.editing()

    def update(self):
        """
        Updates the value displayed in the widget
        :return:
        """
        if not self.widget.hasFocus():
            self.widget.set_list(self.module_value())

    def set_widget(self):
        """
        Sets up the widget (here a ListFloatSpinBox)
        :return:
        """

        self.widget = ListComplexSpinBox(self.number,
                                         label=None,
                                         min=-65e6,
                                         max=65e6,
                                         log_increment=True,
                                         halflife_seconds=1.)
        #self.widget.setDecimals(4)
        #self.widget.setSingleStep(0.01)
        self.widget.value_changed.connect(self.write)


class ListComboBox(QtGui.QWidget):
    value_changed = QtCore.pyqtSignal()

    def __init__(self, number, name, options):
        super(ListComboBox, self).__init__()
        self.setToolTip("First order filter frequencies \n"
                        "negative values are for high-pass \n"
                        "positive for low pass")
        self.lay = QtGui.QHBoxLayout()
        self.lay.setContentsMargins(0,0,0,0)
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

    def update(self):
        """
        Sets the gui value from the current module value

        :return:
        """

        val = getattr(self.module, self.name)
        if isinstance(val, basestring) or not np.iterable(val): # only 1 element in the FilterAttribute, make a list for consistency
            val = [val]
        self.widget.set_list(val)

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
        if self.acquisition_property:
            self.value_changed.emit()

    def update(self):
        """
        Sets the gui value from the current module value

        :return:
        """

        index = list(self.options).index(getattr(self.module, self.name))
        self.widget.setCurrentIndex(index)

class PhaseAttributeWidget(FloatAttributeWidget):
    pass

class FrequencyAttributeWidget(FloatAttributeWidget):
    pass

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


    def update(self):
        """
        Sets the gui value from the current module value

        :return:
        """

        self.widget.setCheckState(getattr(self.module, self.name) * 2)
