"""
RegisterWidgets' hierarchy is parrallel to Registers' hierarchy
An instance of Register can create its RegisterWidget counterPart by calling reg.create_widget(name, parent)
The resulting widget is then saved as an attribute of the register
"""

from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import time

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
    timer_min_interval = 5 # don't go below 5 ms
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

        self.setMaximumWidth(200)
        self.setMaximumHeight(34)

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

    def setMaximum(self, val):
        self.max = val

    def setMinimum(self, val):
        self.min = val

    def setSingleStep(self, val):
        self.step = val

    def setValue(self, val):
        self.val = val

    def setDecimals(self, val):
        self.decimals = val

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
            self.val += self.increment*factor

    def step_down(self, factor=1):
        if self.log_increment:
            val = self.val
            res =  val / self.log_factor() - np.sign(val)*self.increment/10.  # to prevent rounding errors from
                                                                         # blocking the increment
            self.val = res #(self.log_step)**factor
        else:
            self.val -= self.increment*factor

    def make_step_continuous(self):
        """

        :return:
        """
        self.make_step()
        self.timer_arrow.start()
        self.timer_arrow.setInterval(self.best_wait_time())

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
                # mouse
            if event.key()==QtCore.Qt.Key_Down:
                self._button_down_down = True
            self.first_increment()

    def keyReleaseEvent(self, event):
        if not event.isAutoRepeat():
            if event.key()==QtCore.Qt.Key_Up:
                self._button_up_down = False
                # mouse
            if event.key()==QtCore.Qt.Key_Down:
                self._button_down_down = False
            self.timer_arrow.stop()

    def validate(self):
        if self.val>self.max:
            self.val = self.max
        if self.val<self.min:
            self.val = self.min
        self.value_changed.emit()


class MyDoubleSpinBox(MyNumberSpinBox):
    def __init__(self, label, min=-1, max=1, step=2.**(-13),
                 log_increment=False, log_step=1.01):
        self.decimals = 4
        super(MyDoubleSpinBox, self).__init__(label, min, max, step, log_increment, log_step)

    @property
    def val(self):
        if self.line.text()!=("%."+str(self.decimals) + "f")%self._val:
            return float(self.line.text())
        return self._val

    @val.setter
    def val(self, new_val):
        self._val = new_val
        self.line.setText(("%."+str(self.decimals) + "f")%new_val)
        return new_val


class MyIntSpinBox(MyNumberSpinBox):
    def __init__(self, label, min=-2**13, max=2**13, step=1,
                 log_increment=False, log_step=10):
        super(MyIntSpinBox, self).__init__(label,
                                           min,
                                           max,
                                           step,
                                           log_increment,
                                           log_step)

    @property
    def val(self):
        if self.line.text()!=("%.i")%self._val:
            return int(self.line.text())
        return self._val

    @val.setter
    def val(self, new_val):
        self._val = new_val
        self.line.setText(("%.i")%new_val)
        return new_val



class BaseRegisterWidget(QtCore.QObject):
    """
    Base class for GUI properties
    """
    value_changed = QtCore.pyqtSignal()

    def __init__(self, name, module):
        super(BaseRegisterWidget, self).__init__()
        self.module = module
        self.name = name
        self.acquisition_property = True  # property affects signal acquisition
        self.layout_v = QtGui.QVBoxLayout()
        self.label = QtGui.QLabel(name)
        self.layout_v.addWidget(self.label)
        #self.module = self.module_widget.module
        self.set_widget()
        self.layout_v.addWidget(self.widget)

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


class StringRegisterWidget(BaseRegisterWidget):
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


class NumberRegisterWidget(BaseRegisterWidget):
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


class IntRegisterWidget(NumberRegisterWidget):
    """
    Property for integer values.
    """

    def set_widget(self):
        """
        Sets up the widget (here a QSpinBox)
        :return:
        """

        self.widget = MyIntSpinBox(None)#QtGui.QSpinBox()
        #self.widget.setSingleStep(1)
        self.widget.value_changed.connect(self.write)

    def module_value(self):
        """
        returns the module value, with the good type conversion.

        :return: int
        """

        return int(getattr(self.module, self.name))


class FloatRegisterWidget(NumberRegisterWidget):
    """
    Property for float values
    """

    def set_widget(self):
        """
        Sets up the widget (here a QDoubleSpinBox)
        :return:
        """

        self.widget = MyDoubleSpinBox(None)#QtGui.QDoubleSpinBox()
        #self.widget.setDecimals(4)
        #self.widget.setSingleStep(0.01)
        self.widget.value_changed.connect(self.write)

    def module_value(self):
        """
        returns the module value, with the good type conversion.

        :return: float
        """

        return float(getattr(self.module, self.name))


class ListComboBox(QtGui.QWidget):
    value_changed = QtCore.pyqtSignal()

    def __init__(self, number, name, options):
        super(ListComboBox, self).__init__()
        self.lay = QtGui.QHBoxLayout()
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


class FilterRegisterWidget(BaseRegisterWidget):
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
        super(FilterRegisterWidget, self).__init__(name, module)

#    @property
#    def options(self):
#        """
#        All possible options (as found in module.prop_name + 's')
#
#        :return:
#        """
#        return getattr(self.module, self.defaults)

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

    def module_value(self):
        """
        returns the module value, with the good type conversion.

        :return: float
        """

        return self.widget.get_list()

    def update(self):
        """
        Sets the gui value from the current module value

        :return:
        """

        self.widget.set_list(getattr(self.module, self.name))

class SelectRegisterWidget(BaseRegisterWidget):
    """
    Multiple choice property.
    """

    def __init__(self, name, module, defaults=None):
        if defaults is not None:
            self.defaults = defaults
        else:
            self.defaults = name + 's'
        super(SelectRegisterWidget, self).__init__(name, module)

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

class PhaseRegisterWidget(FloatRegisterWidget):
    pass

class FrequencyRegisterWidget(FloatRegisterWidget):
    pass

class BoolRegisterWidget(BaseRegisterWidget):
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
