"""
RegisterWidgets' hierarchy is parrallel to Registers' hierarchy
An instance of Register can create its RegisterWidget counterPart by calling reg.create_widget(name, parent)
The resulting widget is then saved as an attribute of the register
"""

#from pyrpl import RedPitaya
#from pyrpl.hardware_modules import NotReadyError
#from pyrpl.network_analyzer import NetworkAnalyzer
#from pyrpl.spectrum_analyzer import SpectrumAnalyzer
#from pyrpl import CurveDB
from pyrpl.pyrpl_utils import MyDoubleSpinBox, MyIntSpinBox

from time import time
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import numpy as np
from collections import OrderedDict

import sys
if sys.version_info < (3,):
    integer_types = (int, long)
else:
    integer_types = (int,)

APP = QtGui.QApplication.instance()
if APP is None:
    APP = QtGui.QApplication(["redpitaya_gui"])


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

    def set_increment(self, val):
        self.widget.setSingleStep(val)

    def set_maximum(self, val):
        self.widget.setMaximum(val)

    def set_minimum(self, val):
        self.widget.setMinimum(val)


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
