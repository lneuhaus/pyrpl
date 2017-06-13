"""
AttributeWidgets' hierarchy is parallel to Attribute' hierarchy

An instance attr of Attribute can create its AttributeWidget counterPart
by calling attr.create_widget(name, parent).
"""

from pyqtgraph.Qt import QtGui, QtCore
import numpy as np
import time
import functools
import pyqtgraph as pg
from ..pyrpl_utils import Bijection, recursive_setattr, recursive_getattr
from .. import pyrpl_utils
from ..curvedb import CurveDB
from .spinbox import *

# TODO
# why does write emit a signal?
# avoid duplicating set_min, set_increment, and rather retrieve value from descriptiors

# TODO: try to remove widget_name from here (again)


class BaseAttributeWidget(QtGui.QWidget):
    """
    Base class for attribute widgets.

    The widget usually contains a label and a subwidget (property 'widget'
    of the instance), corresponding to the associated attribute. The subwidget
    is the created by the function make_widget.

    AttributeWidgets are always contained in a ModuleWidget and should be
    fully managed by this ModuleWidget.

    If widget_name=="", then only the subwidget is shown without label.

    A minimum widget should implmenet set_widget, _update,
    and possibly module_value.
    """
    value_changed = QtCore.pyqtSignal()

    def __init__(self, module, attribute_name, widget_name=None):
        super(BaseAttributeWidget, self).__init__()
        self.module = module
        self.attribute_name = attribute_name
        if widget_name is None:
            self.widget_name = self.attribute_name
        else:
            self.widget_name = widget_name
        self.setToolTip(self.attribute_descriptor.__doc__)
        self.layout_v = QtGui.QVBoxLayout()
        if self.widget_name != "":
            self.label = QtGui.QLabel(self.widget_name)
            self.layout_v.addWidget(self.label, 0) # stretch=0
        self.layout_v.setContentsMargins(0, 0, 0, 0)
        self._make_widget()
        self.layout_v.addWidget(self.widget, 0) # stretch=0
        self.layout_v.addStretch(1)
        self.setLayout(self.layout_v)
        current_value = self.attribute_value
        if current_value is not None: # SelectAttributes might have a None value
            self.widget_value = current_value
        # this is very nice for debugging, but should probably be removed later
        setattr(self.module, '_'+self.attribute_name+'_widget', self)

    @property
    def attribute_descriptor(self):
        return getattr(self.module.__class__, self.attribute_name)

    @property
    def attribute_value(self):
        return getattr(self.module, self.attribute_name)

    @attribute_value.setter
    def attribute_value(self, v):
        setattr(self.module, self.attribute_name, v)

    @property
    def widget_value(self):
        """ Property for the current value of the widget.

        The associated setter takes care of not re-emitting signals when the
        gui value is modified through the setter. """
        return self._get_widget_value()

    @widget_value.setter
    def widget_value(self, v):
        if not self.widget.hasFocus():
            try:
                self.widget.blockSignals(True)
                self._set_widget_value(v)
            finally:
                self.widget.blockSignals(False)

    def write(self):
        self.attribute_value = self.widget_value
        self.value_changed.emit()  #TODO: check if needed

    def editing(self):
        """
        User is editing the property graphically don't mess up with him
        :return:
        """
        return self.widget.editing()

    def set_horizontal(self):
        """ puts the label to the left of the widget instead of atop """
        self.layout_v.removeWidget(self.label)
        self.layout_v.removeWidget(self.widget)
        self.layout_h = QtGui.QHBoxLayout()
        self.layout_h.addWidget(self.label)
        self.layout_h.addWidget(self.widget)
        self.layout_v.addLayout(self.layout_h)

    def _make_widget(self):
        """
        create the new widget.

        Overwrite in derived class.
        """
        self.widget = None

    def _get_widget_value(self):
        """
        returns the current value shown by the widget.

        The type that is returned is understood by the underlying attribute.

        Overwrite in derived class.
        """
        return self.widget.value()

    def _set_widget_value(self, new_value):
        """
        Changes the value displayed in the widget.

        Overwrite in derived class.
        """
        self.widget.setValue(new_value)


class StringAttributeWidget(BaseAttributeWidget):
    """
    Widget for string values.
    """
    def _make_widget(self):
        self.widget = QtGui.QLineEdit()
        self.widget.setMaximumWidth(200)
        self.widget.textChanged.connect(self.write)

    def _get_widget_value(self):
        return str(self.widget.text())

    def _set_widget_value(self, new_value):
        self.widget.setText(new_value)


class TextAttributeWidget(StringAttributeWidget):
    """
    Property for multiline string values.
    """
    def _make_widget(self):
        self.widget = QtGui.QTextEdit()
        self.widget.textChanged.connect(self.write)

    def _get_widget_value(self):
        return str(self.widget.toPlainText())


class NumberAttributeWidget(BaseAttributeWidget):
    """
    Base widget for float and int.
    """
    def _get_widget_value(self):
        return self.widget.value()

    def editing(self):
        return self.widget.line.hasFocus()

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
    def _make_widget(self):
        """
        Sets up the widget (here a QSpinBox)
        :return:
        """
        self.widget = IntSpinBox(None)#QtGui.QSpinBox()
        # self.widget.setMaximumWidth(200)
        self.widget.value_changed.connect(self.write)


class FloatAttributeWidget(NumberAttributeWidget):
    """
    Property for float values
    """
    def _make_widget(self):
        self.widget = FloatSpinBox(None)
        self.widget.value_changed.connect(self.write)


class FrequencyAttributeWidget(FloatAttributeWidget):
    def __init__(self, module, attribute_name, widget_name=None):
        super(FrequencyAttributeWidget, self).__init__(module,
                                                       attribute_name,
                                                       widget_name=widget_name)
        self.set_per_second(10)


class BasePropertyListPropertyWidget(BaseAttributeWidget):
    """
    A widget for a list of Attributes, deriving its functionality from the
    underlying widgets
    """
    value_changed = QtCore.pyqtSignal()

    @property
    def element_widget(self):
        return self.attribute_descriptor.element_cls._widget_class

    def _make_widget(self):
        self.widget = QtGui.QFrame()
        self.widgets = []
        self.button_add = QtGui.QPushButton("+")
        self.button_add.clicked.connect(self.add_spin_and_select)
        self.widget.addWidget(self.button_add)
        self.widget.addStretch(1)
        self.widget.setContentsMargins(0, 0, 0, 0)
        self.selected = None
        self.widget.value_changed.connect(self.write)

    def __init__(self,
                 label,
                 min=-62.5e6,
                 max=62.5e6,
                 increment=1.,
                 log_increment=True,
                 halflife_seconds=1.,
                 spinbox=None):
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
        # for i in range(number):
        #    self.add_spin()
        self.button_add = QtGui.QPushButton("+")
        self.button_add.clicked.connect(self.add_spin_and_select)
        self.lay.addWidget(self.button_add)
        self.lay.addStretch(1)
        self.lay.setContentsMargins(0, 0, 0, 0)
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
            # self.spins[-1].val = -1e4 -1j*1e3
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
            button_remove.clicked.connect(
                functools.partial(self.remove_spin_and_emit,
                                  button=button_remove))
            self.lay.insertLayout(index + 1 * (self.label is not None),
                                  spin_lay)  # QLabel occupies the first row
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
                if index >= len(self.spins):
                    self.add_spin()
                self.spins[index].val = val
            to_delete = []
            for other_index in range(len(list_val), len(self.spins)):
                to_delete.append(self.button_removes[
                                     other_index])  # don't loop on a list that is
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

    def _get_widget_value(self):
        #return [w.
        pass

    def _set_widget_value(self, new_value):
        self.widget.set_list(new_value)

    def editing(self):
        return self.widget.editing()

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


class ListAttributeWidget(BaseAttributeWidget):
    """
    A widget for ListAttribute
    This class is nearly identical with ListComplexAttributeWidget
    and the two should be merged together
    """
    ListSpinBox = ListFloatSpinBox
    listspinboxkwargs = dict(label=None,
                             min=-62.5e6,
                             max=62.5e6,
                             log_increment=True,
                             halflife_seconds=1.)

    def _make_widget(self):
        """
        Sets up the widget (here a ListFloatSpinBox)
        :return:
        """
        self.widget = self.ListSpinBox(**self.listspinboxkwargs)
        self.widget.value_changed.connect(self.write)

    def _get_widget_value(self):
        return self.widget.get_list()

    def _set_widget_value(self, new_value):
        self.widget.set_list(new_value)

    def editing(self):
        return self.widget.editing()

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


class ListComboBox(QtGui.QWidget):
    # TODO: can be replaced by SelectAttributeWidget
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
    def __init__(self, module, attribute_name, widget_name=None):
        val = getattr(module, attribute_name)
        if np.iterable(val):
            self.number = len(val)
        else:
            self.number = 1
        self.options = getattr(module.__class__, attribute_name).valid_frequencies(module)
        super(FilterAttributeWidget, self).__init__(module, attribute_name,
                                                    widget_name=widget_name)

    def _make_widget(self):
        """
        Sets up the widget (here a QDoubleSpinBox)
        :return:
        """
        self.widget = ListComboBox(self.number, "", list(map(str, self.options)))
        self.widget.value_changed.connect(self.write)

    def _get_widget_value(self):
        return self.widget.get_list()

    def _set_widget_value(self, new_value):
        if isinstance(new_value, str) or not np.iterable(new_value):  # only 1
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
    def _make_widget(self):
        self.widget = QtGui.QComboBox()
        self.widget.addItems(self.options)
        self.widget.currentIndexChanged.connect(self.write)

    @property
    def options(self):
        opt = self.attribute_descriptor.options(self.module).keys()
        opt = [str(v) for v in opt]
        if len(opt) == 0:
            opt = [""]
        return opt

    def _get_widget_value(self):
        return str(self.widget.currentText())
        #try:
        #    return str(self.widget.currentText())
        # except ValueError as e1:
        #     # typically string - int - conversion related
        #     options = self.options
        #     try:
        #         index = [str(k) for k in options].index(str(self.widget.currentText()))
        #     except ValueError as e2:
        #         raise e1
        #     else:
        #         setattr(self.module, self.attribute_name, options[index])

    def _set_widget_value(self, new_value):
        try:
            index = self.options.index(str(new_value))
        except (IndexError, ValueError):
            self.module._logger.warning("SelectWidget %s could not find "
                                        "current value %s in the options %s",
                                        self.attribute_name,
                                        new_value,
                                        self.options)
            index = 0
        self.widget.setCurrentIndex(index)

    def change_options(self, new_options=None):
        """
        The options of the combobox can be changed dynamically.

        new_options is an argument that is ignored, since the new options
        are available as a property to the widget already.
        """
        self.widget.blockSignals(True)
        #self.defaults = new_options
        self.widget.clear()
        #self.widget.addItems(new_options)
        # do not trust the new options, rather call options again
        self.widget.addItems(self.options)
        self.widget_value = self.attribute_value
        self.widget.blockSignals(False)


class LedAttributeWidget(BaseAttributeWidget):
    """ Boolean property with a button whose text and color indicates whether """
    def _make_widget(self):
        desc = recursive_getattr(self.module, '__class__.' + self.attribute_name)
        val = recursive_getattr(self.module, self.attribute_name)
        self.widget = QtGui.QPushButton("setting up...")
        self.widget.clicked.connect(self.button_clicked)

    def _set_widget_value(self, new_value):
        if new_value == True:
            color = 'green'
            text = 'stop'
        else:
            color = 'red'
            text = 'start'
        self.widget.setStyleSheet("background-color:%s"%color)
        self.widget.setText(text)

    def button_clicked(self):
        self.attribute_value = not self.attribute_value


class BoolAttributeWidget(BaseAttributeWidget):
    """
    Checkbox for boolean attributes
    """
    def _make_widget(self):
        self.widget = QtGui.QCheckBox()
        self.widget.stateChanged.connect(self.write)

    def _get_widget_value(self):
        return (self.widget.checkState() == 2)

    def _set_widget_value(self, new_value):
        self.widget.setCheckState(new_value * 2)


class BoolIgnoreAttributeWidget(BoolAttributeWidget):
    """
    Like BoolAttributeWidget with additional option 'ignore' that is
    shown as a grey check in GUI
    """
    _gui_to_attribute_mapping = Bijection({0: False,
                                           1: 'ignore',
                                           2: True})

    def _make_widget(self):
        """
        Sets the widget (here a QCheckbox)
        :return:
        """
        self.widget = QtGui.QCheckBox()
        self.widget.setTristate(True)
        self.widget.stateChanged.connect(self.write)
        self.setToolTip("Checked:\t    on\nUnchecked: off\nGrey:\t    ignore")

    def _get_widget_value(self):
        return self._gui_to_attribute_mapping[self.widget.checkState()]

    def _set_widget_value(self, new_value):
        self.widget.setCheckState(
            self._gui_to_attribute_mapping.inverse[new_value])


class PlotAttributeWidget(BaseAttributeWidget):
    _defaultcolors = ['g', 'r', 'b', 'y', 'c', 'm', 'o', 'w']

    def time(self):
        return pyrpl_utils.time()

    def _make_widget(self):
        """
        Sets the widget (here a QCheckbox)
        :return:
        """
        self.widget = pg.GraphicsWindow(title="Plot")
        legend = getattr(self.module.__class__, self.attribute_name).legend
        self.pw = self.widget.addPlot(title="%s vs. time (s)"%legend)
        self.plot_start_time = self.time()
        self.curves = {}
        setattr(self.module.__class__, '_' + self.attribute_name + '_pw', self.pw)

    def _set_widget_value(self, new_value):
        try:
            args, kwargs = new_value
        except:
            if isinstance(new_value, dict):
                args, kwargs = [], new_value
            elif isinstance(new_value, list):
                args, kwargs = new_value, {}
            else:
                args, kwargs = [new_value], {}
        for k in kwargs.keys():
            v = kwargs.pop(k)
            kwargs[k[0]] = v
        i=0
        for value in args:
            while self._defaultcolors[i] in kwargs:
                i += 1
            kwargs[self._defaultcolors[i]] = value
        t = self.time()-self.plot_start_time
        for color, value in kwargs.items():
            if value is not None:
                if not color in self.curves:
                    self.curves[color] = self.pw.plot(pen=color)
                curve = self.curves[color]
                x, y = curve.getData()
                if x is None or y is None:
                    x, y = np.array([t]), np.array([value])
                else:
                    x, y = np.append(x, t), np.append(y, value)
                curve.setData(x, y)

    def _magnitude(self, data):
        """ little helpers """
        return 20. * np.log10(np.abs(data) + sys.float_info.epsilon)

    def _phase(self, data):
        """ little helpers """
        return np.angle(data, deg=True)


class CurveAttributeWidget(PlotAttributeWidget):
    """
    Base property for float and int.
    """
    def _make_widget(self):
        self.widget = pg.GraphicsWindow(title="Curve")
        self.plot_item = self.widget.addPlot(title="Curve")
        self.plot_item_phase = self.widget.addPlot(row=1, col=0, title="Phase (deg)")
        self.plot_item_phase.setXLink(self.plot_item)
        self.plot_item.showGrid(y=True, alpha=1.)
        self.plot_item_phase.showGrid(y=True, alpha=1.)
        self.curve = self.plot_item.plot(pen='g')
        self.curve_phase = self.plot_item_phase.plot(pen='g')

    def _set_widget_value(self, new_value):
        if new_value is None:
            return
        try:
            data = getattr(self.module, '_' + self.attribute_name + '_object').data
            name = getattr(self.module, '_' + self.attribute_name + '_object').params['name']
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


class CurveSelectAttributeWidget(SelectAttributeWidget):
    """
    Select one or many curves.
    """
    def _make_widget(self):
        """
        Sets up the widget (here a QComboBox)

        :return:
        """
        self.widget = QtGui.QListWidget()
        self.widget.addItems(self.options)
        self.widget.currentItemChanged.connect(self.write)

    def _get_widget_value(self):
        return int(self.widget.currentItem().text())

    def _set_widget_value(self, new_value):
        """ should be much simpler here. all this logic should be in the
        attribute """
        if new_value is None:
            new_value = -1
        if hasattr(new_value, 'pk'):
            new_value = new_value.pk
        try:
            index = self.options.index(str(new_value))
        except IndexError:
            self.module._logger.warning("SelectWidget %s could not find "
                                        "current value %s in the options %s",
                                        self.attribute_name, self.new_value, self.options)
            index = 0
        self.widget.setCurrentRow(index)
