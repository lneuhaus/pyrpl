from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import NotReadyError
from pyrpl.network_analyzer import NetworkAnalyzer
from pyrpl.spectrum_analyzer import SpectrumAnalyzer
from pyrpl import CurveDB
from pyrpl.pyrpl_utils import MyDoubleSpinBox

from time import time
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import pyqtgraph.console
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


def property_factory(module_widget, prop):
    """
    Tries to match one of the base property types with the attribute of the underlying module.
    If the same attribute name followed by an "s" exists, then a ComboProperty is used.

    :param module_widget:
    :param prop:
    :return: an instance of a class heritating from BaseProperty
    """
    new_prop = None
    attr = getattr(module_widget.module, prop)
    def get_combo(attr, prop, with_s=False):
        if with_s:
            prop_name = prop[:-1] + 's'
        else:
            prop_name = None
        if isinstance(attr, basestring) or not np.iterable(attr):
            return ComboProperty(prop, module_widget, prop_name)
        else:
            return ListComboProperty(prop, module_widget, len(attr))

    if hasattr(module_widget.module, prop + 's'):
        return get_combo(attr, prop)
    elif hasattr(module_widget.module, prop[:-1] + 's') \
            and (prop[:-1] + 's') != prop:  # for instance inputs for input1
        return get_combo(attr, prop, with_s=True)
    else:
        if isinstance(attr, bool):
            new_prop = BoolProperty(prop, module_widget)
        elif isinstance(attr, integer_types):
            new_prop = IntProperty(prop, module_widget)
        elif isinstance(attr, str):
            new_prop = StringProperty(prop, module_widget)
        else:
            new_prop = FloatProperty(prop, module_widget)
    return new_prop


class BaseProperty(QtCore.QObject):
    """
    Base class for GUI properties
    """
    value_changed = QtCore.pyqtSignal()

    def __init__(self, name, module_widget):
        super(BaseProperty, self).__init__()
        self.module_widget = module_widget
        self.name = name
        self.acquisition_property = True  # property affects signal acquisition
        self.layout_v = QtGui.QVBoxLayout()
        self.label = QtGui.QLabel(name)
        self.layout_v.addWidget(self.label)
        self.module = self.module_widget.module
        self.set_widget()
        self.layout_v.addWidget(self.widget)
        self.module_widget.property_layout.addLayout(self.layout_v)
        self.value_changed.connect(self.emit_widget_value_changed)
        #self.module_widget.property_watch_timer.timeout. \
        #    connect(self.update_widget)

    def editing(self):
        """
        User is editing the property graphically don't mess up with him
        :return:
        """
        return False

    def emit_widget_value_changed(self):
        if self.acquisition_property:
            self.module_widget.property_changed.emit()

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


class StringProperty(BaseProperty):
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


class NumberProperty(BaseProperty):
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

class IntProperty(NumberProperty):
    """
    Property for integer values.
    """

    def set_widget(self):
        """
        Sets up the widget (here a QSpinBox)
        :return:
        """

        self.widget = MyDoubleSpinBox(None)#QtGui.QSpinBox()
        #self.widget.setSingleStep(1)
        self.widget.value_changed.connect(self.write)

    def module_value(self):
        """
        returns the module value, with the good type conversion.

        :return: int
        """

        return int(getattr(self.module, self.name))


class FloatProperty(NumberProperty):
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
        for i, v in enumerate(val):
            v = str(int(v))
            index = self.options.index(v)
            self.combos[i].setCurrentIndex(index)

class ListComboProperty(BaseProperty):
    """
    Property for list of floats
    """

    def __init__(self, name, module_widget, number):
        self.number = number
        self.defaults = name + 's'
        super(ListComboProperty, self).__init__(name, module_widget)

    @property
    def options(self):
        """
        All possible options (as found in module.prop_name + 's')

        :return:
        """
        return getattr(self.module, self.defaults)

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

class ComboProperty(BaseProperty):
    """
    Multiple choice property. Defaults is the name of the property
    containing all possibilities in the module (usually name + 's').
    """

    def __init__(self, name, module_widget, defaults=None):
        if defaults is not None:
            self.defaults = defaults
        else:
            self.defaults = name + 's'
        super(ComboProperty, self).__init__(name, module_widget)

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
        return getattr(self.module, self.defaults)

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


class BoolProperty(BaseProperty):
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


class ModuleWidget(QtGui.QWidget):
    """
    Base class for a module Widget. In general, this is one of the Tab in the
    final RedPitayaGui object.
    """

    property_changed = QtCore.pyqtSignal()
    property_names = []
    curve_class = CurveDB


    def __init__(self, name, rp, parent=None, module=None, namespace=None):
        super(ModuleWidget, self).__init__(parent)
        self.rp = rp
        self.name = name
        if module is None:
            module = self
        self.properties = OrderedDict()
        self.module = module
        self.namespace=namespace
        self.init_gui()
        self.update_properties()
        self.rp.all_gui_modules.append(self)

    def get_state(self):
        """returns a dictionary containing all properties listed in
        property_names."""
        #Not sure if we should also set the state of the underlying module

        dic = dict()
        for val in self.property_names:
            dic[val] = getattr(self.module, val)
        return dic

    def set_state(self, dic):
        """Sets the state using a dictionary"""

        for key, val in dic.iteritems():
            setattr(self.module, key, val)
        self.module.setup()


    def stop_all_timers(self):
        self.property_watch_timer.stop()
        try:
            self.timer.stop()
        except AttributeError:
            pass

    def init_property_layout(self):
        """
        Automatically creates the gui properties for the properties in property_names.
        Also sets a 100 ms timer to keep gui values in sync with the underlying module.
        :return:
        """

        self.property_watch_timer = QtCore.QTimer()
        self.property_watch_timer.setInterval(300) # Less would cause some
        # deadlock whith the up/down arrow in log_increment
        self.property_watch_timer.timeout.connect(self.update_properties)
        self.property_watch_timer.start()

        self.property_layout = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.property_layout)

        for prop_name in self.property_names:
            prop = property_factory(self, prop_name)
            self.properties[prop_name] = prop

    def save_curve(self, x_values, y_values, **params):
        """
        Saves the curve in some database system.
        To change the database system, overwrite this function
        or patch Module.curvedb if the interface is identical.

        :param  x_values: numpy array with x values
        :param  y_values: numpy array with y values
        :param  params: extra curve parameters (such as relevant module settings)
        """

        c = self.curve_class.create(x_values,
                                    y_values,
                                    **params)
        return c

    def init_gui(self):
        """
        To be overwritten in derived class

        :return:
        """

        self.main_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.init_property_layout()


    def update_properties(self):
        """
        Updates all properties listed in self.properties

        :return:
        """
        for prop in self.properties.values():
            if not prop.editing():
                prop.update_widget()


class ScopeSaWidget(QtGui.QTabWidget):
    """
    A tab widget that prevents scope and sa to be open at the same time
    """

    def __init__(self, scope_widget, sa_widget):
        super(ScopeSaWidget, self).__init__()
        self.scope_widget = scope_widget
        self.sa_widget = sa_widget

        self.addTab(self.scope_widget, "Scope")
        self.addTab(self.sa_widget, "Spec. an.")

        self.scope_state = self.scope_widget.get_state()
        self.sa_state = self.sa_widget.get_state()

        self.currentChanged.connect(self.reload_state)



    def reload_state(self):
        if self.currentWidget()==self.scope_widget:
            self.sa_state = self.sa_widget.get_state()
            self.scope_widget.set_state(self.scope_state)
            self.sa_widget.stop()
        else:
            self.scope_state = self.scope_widget.get_state()
            self.sa_widget.set_state(self.sa_state)
            self.scope_widget.stop()

class ScopeWidget(ModuleWidget):
    """
    Widget for scope
    """
    property_names = ["input1",
                      "input2",
                      "duration",
                      "average",
                      "trigger_source",
                      "trigger_delay",
                      "threshold_ch1",
                      "threshold_ch2",
                      "curve_name"]

    def init_gui(self):
        """
        sets up all the gui for the scope.
        """

        self.datas = [None, None]
        self.times = None
        self.ch_col = ('green', 'red')
        self.module.__dict__['curve_name'] = 'scope'
        self.main_layout = QtGui.QVBoxLayout()
        self.init_property_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Scope")
        self.win = pg.GraphicsWindow(title="Scope")
        self.plot_item = self.win.addPlot(title="Scope")
        self.plot_item.showGrid(y=True, alpha=1.)
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_save = QtGui.QPushButton("Save curve")
        self.curves = [self.plot_item.plot(pen=color[0]) \
                       for color in self.ch_col]
        self.main_layout.addWidget(self.win)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)
        self.cb_ch = []
        for i in (1, 2):
            self.cb_ch.append(QtGui.QCheckBox("Channel " + str(i)))
            self.button_layout.addWidget(self.cb_ch[-1])

        self.button_single.clicked.connect(self.run_single)
        self.button_continuous.clicked.connect(self.run_continuous_clicked)
        self.button_save.clicked.connect(self.save)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(10)
        self.timer.setSingleShot(True)

        self.timer.timeout.connect(self.check_for_curves)

        for cb, col in zip(self.cb_ch, self.ch_col):
            cb.setCheckState(2)
            cb.setStyleSheet('color: ' + col)
        for cb in self.cb_ch:
            cb.stateChanged.connect(self.display_curves)

        self.rolling_group = QtGui.QGroupBox("Trigger mode")
        self.checkbox_normal = QtGui.QRadioButton("Normal")
        self.checkbox_untrigged = QtGui.QRadioButton("Untrigged (rolling)")
        self.checkbox_normal.setChecked(True)
        self.lay_radio = QtGui.QVBoxLayout()
        self.lay_radio.addWidget(self.checkbox_normal)
        self.lay_radio.addWidget(self.checkbox_untrigged)
        self.rolling_group.setLayout(self.lay_radio)
        self.property_layout.insertWidget(
            self.property_names.index("trigger_source"), self.rolling_group)
        self.checkbox_normal.clicked.connect(self.rolling_mode_toggled)
        self.checkbox_untrigged.clicked.connect(self.rolling_mode_toggled)
        #self.checkbox_normal.enabledChange.connect(self.rolling_mode_toggled)

        # minima maxima
        for prop in (self.properties["threshold_ch1"],
                     self.properties["threshold_ch1"]):
            spin_box = prop.widget
            spin_box.setDecimals(4)
            spin_box.setMaximum(1)
            spin_box.setMinimum(-1)
            spin_box.setSingleStep(0.01)

        self.properties["curve_name"].acquisition_property = False
        # add a console
        self.c = pyqtgraph.console.ConsoleWidget(namespace=self.namespace)
        self.main_layout.addWidget(self.c)

    def display_channel(self, ch):
        """
        Displays channel ch (1 or 2) on the graph
        :param ch:
        """
        try:
            self.datas[ch-1] = self.module.curve(ch)
            self.times = self.module.times
            self.curves[ch - 1].setData(self.times,
                                        self.datas[ch-1])
        except NotReadyError:
            pass

    def display_curves(self):
        """
        Displays all active channels on the graph.
        """

        for i in (1, 2):
            if self.cb_ch[i - 1].checkState() == 2:
                self.display_channel(i)
                self.curves[i - 1].setVisible(True)
            else:
                self.curves[i - 1].setVisible(False)

    def run_single(self):
        """
        When run_single is pressed, launches a single acquisition.
        """

        self.module.setup()
        self.plot_item.enableAutoRange('xy', True)
        self.display_curves()

    def check_for_curves(self):
        """
        This function is called periodically by a timer when in run_continuous mode.
        1/ Check if curves are ready.
        2/ If so, plots them on the graph
        3/ Restarts the timer.
        """

        if not self.rolling_mode:
            if self.module.curve_ready():
                self.display_curves()
                if self.first_shot_of_continuous:
                    self.first_shot_of_continuous = False  # autoscale only upon first curve
                    self.plot_item.enableAutoRange('xy', False)
                self.module.setup()
        else:
            wp0 = self.module._write_pointer_current
            self.datas = [None, None]
            for ch in (1, 2):
                if self.cb_ch[ch - 1].checkState() == 2:
                    self.datas[ch-1] = self.module._get_ch_no_roll(ch)
            wp1 = self.module._write_pointer_current
            for index, data in enumerate(self.datas):
                if data is None:
                    self.curves[index].setVisible(False)
                    continue
                to_discard = (wp1 - wp0) % self.module.data_length
                data = np.roll(data, self.module.data_length - wp0)[
                       to_discard:]
                data = np.concatenate([[np.nan] * to_discard, data])
                times = self.module.times
                times -= times[-1]
                self.datas[index] = data
                self.times = times
                self.curves[index].setData(times, data)
                self.curves[index].setVisible(True)
        try:
            self.curve_display_done()
        except Exception as e:
            print(e)
        self.timer.start()

    def curve_display_done(self):
        """
        User may overwrite this function to implement custom functionality
        at each graphical update.
        :return:
        """
        pass

    @property
    def state(self):
        if self.button_continuous.text()=="Stop":
            return "running"
        else:
            return "stopped"

    def run_continuous(self):
        """
        Toggles the button run_continuous to stop and starts the acquisition timer.
        This function is part of the public interface.
        """

        self.button_continuous.setText("Stop")
        self.button_single.setEnabled(False)
        self.module.setup()
        if self.rolling_mode:
            self.module._trigger_source = 'off'
            self.module._trigger_armed = True
        self.plot_item.enableAutoRange('xy', True)
        self.first_shot_of_continuous = True
        self.timer.start()

    def stop(self):
        """
        Toggles the button stop to run_continuous to stop and stops the acquisition timer
        """

        self.button_continuous.setText("Run continuous")
        self.timer.stop()
        self.button_single.setEnabled(True)

    def run_continuous_clicked(self):
        """
        Toggles the button run_continuous to stop or vice versa and starts the acquisition timer
        """

        if str(self.button_continuous.text()) \
                == "Run continuous":
            self.run_continuous()
        else:
            self.stop()

    def rolling_mode_toggled(self):
        self.rolling_mode = self.rolling_mode

    @property
    def rolling_mode(self):
        return ((self.checkbox_untrigged.isChecked()) and \
                self.rolling_group.isEnabled())

    @rolling_mode.setter
    def rolling_mode(self, val):
        if val:
            self.checkbox_untrigged.setChecked(True)
        else:
            self.checkbox_normal.setChecked(True)
        if self.state=='running':
            self.stop()
            self.run_continuous()
        return val

    def update_properties(self):
        super(ScopeWidget, self).update_properties()

        self.rolling_group.setEnabled(self.module.duration > 0.1)
        self.properties['trigger_source'].widget.setEnabled(
            not self.rolling_mode)
        old = self.properties['threshold_ch1'].widget.isEnabled()
        self.properties['threshold_ch1'].widget.setEnabled(
            not self.rolling_mode)
        self.properties['threshold_ch2'].widget.setEnabled(
            not self.rolling_mode)
        self.button_single.setEnabled(not self.rolling_mode)
        if old==self.rolling_mode:
            self.rolling_mode_toggled()

    def autoscale(self):
        """Autoscale pyqtgraph"""

        self.plot_item.autoRange()
    #@property
    #def params(self):
    #    """
    #    Params to be saved within the curve (maybe we should consider
    #    # removing this and instead
    #    use self.properties...
    #    """
    #    return dict(average=self.module.average,
    #                trigger_source=self.module.trigger_source,
    #                threshold_ch1=self.module.threshold_ch1,
    #                threshold_ch2=self.module.threshold_ch2,
    #                input1=self.module.input1,
    #                input2=self.module.input2,
    #                name=self.module.curve_name)


    def save(self):
        """
        Save the active curve(s). If you would like to overwrite the save behavior, maybe you should
        consider overwriting Module.save_curve or Module.curve_db rather than this function.
        """

        for ch in [1, 2]:
            d = self.get_state()
            d.update({'ch': ch,
                      'name': self.module.curve_name + ' ch' + str(ch)})
            self.save_curve(self.times,
                            self.datas[ch-1],
                            **d)


class AsgGui(ModuleWidget):
    """
    Widget for a single Asg. Several of these are piled up in the Asg Tab.
    """

    property_names = ["waveform",
                      "amplitude",
                      "offset",
                      "frequency",
                      "trigger_source",
                      "output_direct"]

    def init_gui(self):
        """
        Sets up the gui.
        """

        self.main_layout = QtGui.QVBoxLayout()
        self.init_property_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Asg")
        """
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.curves = [self.plot_item.plot(pen=color[0]) \
                       for color in self.ch_col]
        """
        self.main_layout.addLayout(self.button_layout)
        self.cb_ch = []

        freq_spin_box = self.properties["frequency"].widget
        freq_spin_box.setDecimals(1)
        freq_spin_box.setMaximum(100e6)
        freq_spin_box.setMinimum(-100e6)
        freq_spin_box.setSingleStep(100)

        self.properties["offset"].widget.setMaximum(1)
        self.properties["offset"].widget.setMinimum(-1)

        self.properties['trigger_source'].value_changed.connect(
                                                        self.module.setup)
        self.properties['output_direct'].value_changed.connect(
                                                        self.module.setup)


class AllAsgGui(QtGui.QWidget):
    """
    The Tab widget containing all the Asg
    """

    def __init__(self, parent=None, rp=None):
        super(AllAsgGui, self).__init__(parent)
        self.rp = rp
        self.asg_widgets = []
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)
        nr = 1
        self.layout.setAlignment(QtCore.Qt.AlignTop)

        while hasattr(self.rp, "asg" + str(nr)):
            widget = AsgGui(name="asg" + str(nr),
                            rp=self.rp,
                            parent=None,
                            module=getattr(self.rp, "asg" + str(nr)))
            self.asg_widgets.append(widget)
            self.layout.addWidget(widget)
            nr += 1
            self.layout.setStretchFactor(widget, 0)


class AveragingError(Exception):
    pass


class NaGui(ModuleWidget):
    """
    Network Analyzer Tab.
    """
    property_names = ["input",
                      "output_direct",
                      "start",
                      "stop",
                      "rbw",
                      "points",
                      "amplitude",
                      "logscale",
                      "infer_open_loop_tf",
                      "avg",
                      "curve_name"]

    def init_gui(self):
        """
        Sets up the gui
        """
        # add this new display parameter to module na
        self.module.infer_open_loop_tf = False
        self.module.__dict__['curve_name'] = 'na trace'
        self.main_layout = QtGui.QVBoxLayout()
        self.init_property_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("NA")
        self.win = pg.GraphicsWindow(title="Amplitude")
        self.win_phase = pg.GraphicsWindow(title="Phase")
        self.plot_item = self.win.addPlot(title="Magnitude (dB)")
        self.plot_item_phase = self.win_phase.addPlot(title="Phase (deg)")
        self.plot_item_phase.setXLink(self.plot_item)
        self.button_single = QtGui.QPushButton("Run single")
        self.button_single.my_label = "Single"
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_continuous.my_label = "Continuous"
        self.button_restart_averaging = QtGui.QPushButton('Restart averaging')

        self.button_save = QtGui.QPushButton("Save curve")

        self.curve = self.plot_item.plot(pen='y')
        self.curve_phase = self.plot_item_phase.plot(pen=None, symbol='o')
        self.main_layout.addWidget(self.win)
        self.main_layout.addWidget(self.win_phase)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_restart_averaging)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)

        self.button_single.clicked.connect(self.run_single_clicked)
        self.button_continuous.clicked.connect(self.run_continuous_clicked)
        self.button_restart_averaging.clicked.connect(
            self.ask_restart_and_do_it)
        self.button_save.clicked.connect(self.save)
        self.timer = QtCore.QTimer()  # timer for point acquisition
        self.timer.setInterval(10)
        self.timer.setSingleShot(True)

        self.update_timer = QtCore.QTimer()  # timer for plot update
        self.update_timer.setInterval(50)  # 50 ms refreshrate max
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.setSingleShot(True)

        self.continuous = True
        self.paused = True
        self.need_restart = True

        self.property_changed.connect(self.ask_restart)

        self.timer.timeout.connect(self.add_one_point)

        self.paused = True
        # self.restart_averaging() # why would you want to do that? Comment?

        for prop in (self.properties["start"],
                     self.properties["stop"],
                     self.properties["rbw"]):
            spin_box = prop.widget
            # spin_box.setDecimals(1)
            spin_box.setMaximum(100e6)
            spin_box.setMinimum(-100e6)
            spin_box.setSingleStep(100)
        for prop in (self.properties["points"], self.properties["avg"]):
            spin_box = prop.widget
            spin_box.setMaximum(1e6)
            spin_box.setMinimum(0)

        self.properties["infer_open_loop_tf"].acquisition_property = False
        self.properties["curve_name"].acquisition_property = False

        self.arrow = pg.ArrowItem()
        self.arrow.setVisible(False)
        self.arrow_phase = pg.ArrowItem()
        self.arrow_phase.setVisible(False)
        self.plot_item.addItem(self.arrow)
        self.plot_item_phase.addItem(self.arrow_phase)

    def save_params(self):
        """
        Stores the params in a dictionary self.params.
        We should consider using self.properties instead of manually iterating.
        """

        self.params = self.get_state()
        """
        self.params = dict(start=self.module.start,
                                   stop=self.module.stop,
                                   rbw=self.module.rbw,
                                   input=self.module.input,
                                   output_direct=self.module.output_direct,
                                   points=self.module.points,
                                   amplitude=self.module.amplitude,
                                   logscale=self.module.logscale,
                                   avg=self.module.avg,
                                   post_average=self.post_average,
                                   infer_open_loop_tf=self.module.infer_open_loop_tf,
                                   name=self.module.curve_name)
        """
    def save(self):
        """
        Save the current curve. If you would like to overwrite the save behavior, maybe you should
        consider overwriting Module.save_curve or Module.curve_db rather than this function.
        """

        self.save_curve(self.x[:self.last_valid_point],
                        self.data[:self.last_valid_point],
                        **self.params)

    def init_data(self):
        """
        Prepares empty arrays before starting the scan
        """

        self.data = np.zeros(self.module.points, dtype=complex)
        self.x = np.empty(self.module.points)
        self.post_average = 0

    def ask_restart(self):
        """
        Called whenever a property is changed: the execution should stop and
        when the user wants to acquire more, the acquisition should restart
        from scratch. However, the current curve is not immediately erased in
        case the user would like to save it.
        """

        self.set_state(continuous=self.continuous, paused=True,
                       need_restart=True, n_av=0)

    def ask_restart_and_do_it(self):
        """
        Restart is actually done immediately (Called when the user clicks on restart averaging)
        """

        if not self.paused:
            self.timer.stop()
            self.restart_averaging()
            self.new_run()
            self.timer.start()
            self.set_state(continuous=self.continuous, paused=self.paused,
                           need_restart=False, n_av=0)
        else:
            self.set_state(continuous=self.continuous, paused=self.paused,
                           need_restart=True, n_av=0)

    def restart_averaging(self):
        """
        Initializes the data, sets the timer, launches the run.
        """

        self.init_data()
        self.timer.setInterval(self.module.time_per_point * 1000)
        self.update_timer.setInterval(10)
        self.new_run()

    def run_single(self):
        """
        Launches a single run (part of the public interface).
        Restarts averaging from scratch.
        """

        self.restart_averaging()
        self.new_run()
        self.set_state(continuous=False, paused=False, need_restart=False)
        self.timer.start()

    def run_single_clicked(self):
        """
        Toggles between pause and running.
        """
        if self.paused:
            if self.continuous or self.need_restart:  # restart from scratch
                self.run_single()
            else:  # continue with the previously started scan
                self.set_state(continuous=False, paused=False,
                               need_restart=False)
                self.timer.start()
        else:  # If already running, then set to paused
            self.set_state(continuous=False, paused=True, need_restart=False)

    def stop(self):
        """
        Stop the current execution (part of the public interface).
        """

        self.set_state(continuous=self.continuous, paused=True,
                       need_restart=self.need_restart)
        self.module.iq.amplitude = 0

    def new_run(self):
        """
        Sets up the fpga modules for a new run and save the run parameters.
        """

        self.module.setup()
        self.values = self.module.values()
        self.save_params()

    def set_state(self, continuous, paused, need_restart, n_av=0):
        """
        The current state is composed of 3 flags and a number. This function
        updates the flags and reflects on the gui the required state.

        :param continuous: True or False means continuous or single
        :param paused: True or False Whether the acquisition is running or stopped
        :param need_restart: True or False: whether the current data could be averaged with upcoming ones
        :param n_av: current number of averages
        :return:
        """

        self.continuous = continuous
        self.paused = paused
        self.need_restart = need_restart
        active_button = self.button_continuous if continuous else self.button_single
        inactive_button = self.button_single if continuous else self.button_continuous
        self.button_restart_averaging.setEnabled(not need_restart)
        active_button.setEnabled(True)
        inactive_button.setEnabled(self.paused)
        first_word = 'Run ' if need_restart else 'Continue '
        if self.paused:
            self.button_single.setText("Run single")
            self.button_continuous.setText(first_word + "(%i averages)" % n_av)
            self.module.iq.amplitude = 0
        else:
            if active_button == self.button_single:
                active_button.setText('Pause')
            else:
                active_button.setText('Pause (%i averages)' % n_av)

    @property
    def last_valid_point(self):
        """
        Index of the last point that contains more than 0 averages
        """
        if self.post_average > 0:
            max_point = self.module.points
        else:
            max_point = self.module.current_point
        return max_point

    def threshold_hook(self, current_val):
        """
        A convenience function to stop the run upon some condition
        (such as reaching of a threshold. current_val is the complex amplitude
        of the last data point).

        To be overwritten in derived class...
        Parameters
        ----------
        current_val

        Returns
        -------

        """
        pass

    def update_plot(self):
        """
        Update plot only every 10 ms max...

        Returns
        -------
        """
        # plot_time_start = time()
        x = self.x[:self.last_valid_point]
        y = self.data[:self.last_valid_point]

        # check if we shall display open loop tf
        if self.properties["infer_open_loop_tf"].widget.checkState() == 2:
            y = y / (1.0 + y)
        mag = 20 * np.log10(np.abs(y))
        phase = np.angle(y, deg=True)
        log_mod = self.module.logscale
        self.curve.setLogMode(xMode=log_mod, yMode=None)
        self.curve_phase.setLogMode(xMode=log_mod, yMode=None)

        self.plot_item.setLogMode(x=log_mod, y=None) # this seems also needed
        self.plot_item_phase.setLogMode(x=log_mod, y=None)

        self.curve.setData(x, mag)
        self.curve_phase.setData(x, phase)

        cur = self.module.current_point - 1
        visible = self.last_valid_point!=cur + 1
        logscale = self.properties["logscale"].widget.checkState()==2
        freq = x[cur]
        xpos = np.log10(freq) if logscale else freq
        if cur>0:
            self.arrow.setPos(xpos, mag[cur])
            self.arrow.setVisible(visible)
            self.arrow_phase.setPos(xpos, phase[cur])
            self.arrow_phase.setVisible(visible)
        # plot_time = time() - plot_time_start # actually not working, because done later
        # self.update_timer.setInterval(plot_time*10*1000) # make sure plotting
        # is only marginally slowing
        # down the measurement...
        self.update_timer.setInterval(self.last_valid_point / 100)

    def add_one_point(self):
        """
        This function is called by a timer periodically to add new points in the buffer.
        Plotting is actually done by another independent loop.
        """

        if self.paused:
            return
        cur = self.module.current_point
        try:
            x, y, amp = next(self.values)
            self.threshold_hook(y)
        except StopIteration:
            self.post_average += 1
            if self.continuous:
                self.new_run()
                self.set_state(continuous=True, paused=False,
                               need_restart=False, n_av=self.post_average)
                self.timer.start()
            else:
                self.set_state(continuous=True, paused=True,
                               need_restart=False, n_av=self.post_average)  # 1
                self.button_single.setText("Run single")
            return
        self.data[cur] = (self.data[cur] * self.post_average + y) \
                         / (self.post_average + 1)
        self.x[cur] = x
        # fomerly, we had buffers for both phase and magnitude. This was faster
        # but more messy. We could restore them once the display get
        # exceedingly slow. In that case, they should be calculated right
        # after acquisition, i.e. here.

        if not self.update_timer.isActive():
            self.update_timer.start()

        self.timer.setInterval(self.module.time_per_point * 1000)
        self.timer.start()

    def run_continuous(self):
        """
        Launch a continuous acquisition (part of the public interface).
        Averages from scratch
        """

        self.restart_averaging()
        self.new_run()
        self.set_state(continuous=True, paused=False, need_restart=False,
                       n_av=self.post_average)
        self.timer.start()

    def resume_acquisition(self):
        """
        Resumes the current acquisition (continuous or single) if it was stopped.
        An AveragingError is launched if the parameters have changed in the mean time.
        """

        if self.need_restart:
            raise AveragingError(
                """parameters have changed in the mean time, cannot average
                with previous data""")
        else:
            self.set_state(continuous=self.continuous,
                           paused=False,
                           need_restart=self.need_restart,
                           n_av=self.post_average)

    def run_continuous_clicked(self):
        """
        Toggles the run continuous button, and performs the required action.
        """
        if self.paused:
            if self.need_restart:
                self.run_continuous()
            else:
                self.set_state(continuous=True, paused=False,
                               need_restart=False, n_av=self.post_average)
                self.timer.start()
        else:
            self.set_state(continuous=True, paused=True, need_restart=False,
                           n_av=self.post_average)


class PidGui(ModuleWidget):
    """
    Widget for a single PID.
    """

    property_names = ["input",
                      "output_direct",
                      "setpoint",
                      "p",
                      "i",
                      "d",
                      "ival",
                      "inputfilter"]

    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.init_property_layout()
        layout = self.properties["inputfilter"].layout_v
        self.property_layout.removeItem(layout)
        self.main_layout.addLayout(layout)
        for prop in 'p', 'i', 'd':
            self.properties[prop].widget.set_log_increment()
            self.properties[prop].widget.setMaximum(1000000)
            self.properties[prop].widget.setMinimum(-1000000)


class AllPidGui(QtGui.QWidget):
    def __init__(self, parent=None, rp=None):
        super(AllPidGui, self).__init__(parent)
        self.rp = rp
        self.pid_widgets = []
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)
        nr = 0
        self.layout.setAlignment(QtCore.Qt.AlignTop)

        while hasattr(self.rp, "pid" + str(nr)):
            widget = PidGui(name="pid" + str(nr),
                            rp=self.rp,
                            parent=None,
                            module=getattr(self.rp, "pid" + str(nr)))
            self.pid_widgets.append(widget)
            self.layout.addWidget(widget)
            nr += 1
            self.layout.setStretchFactor(widget, 0)



class SpecAnGui(ModuleWidget):
    """
    Widget for the Spectrum Analyzer Tab.
    """
    _display_max_frequency = 25  # max 25 Hz framerate

    property_names = ["input",
                      "baseband",
                      "center",
                      "span",
                      "points",
                      "rbw_auto",
                      "rbw",
                      "window",
                      "avg",
                      "acbandwidth",
                      "curve_name"]

    def init_gui(self):
        """
        Sets up the gui.
        """
        self.main_layout = QtGui.QVBoxLayout()
        self.module.__dict__['curve_name'] = 'pyrpl spectrum'
        self.init_property_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Spec. An.")
        self.win = pg.GraphicsWindow(title="PSD")
        self.plot_item = self.win.addPlot(title="PSD")
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_restart_averaging = QtGui.QPushButton('Restart averaging')

        self.button_save = QtGui.QPushButton("Save curve")

        self.curve = self.plot_item.plot(pen='m')

        self.main_layout.addWidget(self.win)

        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_restart_averaging)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)

        self.button_single.clicked.connect(self.run_single)
        self.button_continuous.clicked.connect(self.run_continuous_clicked)
        self.button_restart_averaging.clicked.connect(self.restart_averaging)
        self.button_save.clicked.connect(self.save)

        self.timer = QtCore.QTimer()
        # self.timer.setSingleShot(True)
        #  dont know why but this removes the bug with with freezing gui
        self.timer.setSingleShot(False)
        self.timer.setInterval(10)
        self.timer.timeout.connect(self.acquire_one_curve)

        self.running = False
        self.property_changed.connect(self.restart_averaging)

        for prop in [self.properties[prop] for prop in
                     ["center", "rbw"]]:
            prop.widget.setMaximum(125e6)
            prop.widget.setDecimals(0)
        self.properties["acbandwidth"].widget.setMaximum(100e6)
        self.properties["points"].widget.setMaximum(16384)
        self.properties["avg"].widget.setMaximum(1000000000)
        self.properties["curve_name"].acquisition_property = False

    def save(self):
        """
        Saves the current curve.
        """
        self.save_curve(self.x_data,
                        self.module.data_to_dBm(self.y_data),
                        **self.get_state())

    def update_properties(self):
        """
        Updates the gui properties from the underlying module properties.
        Called periodically.
        """

        super(SpecAnGui, self).update_properties()
        self.properties["rbw"].widget.setEnabled(not self.module.rbw_auto)

    @property
    def current_average(self):
        return self._current_average

    @current_average.setter
    def current_average(self, v):
        # putting a ceiling to the current average, together with the math
        # in acquire_one_curve, automatically creates a lowpass-like
        # averaging mode with a 'bandwidth' defined by avg
        if v > self.module.avg:
            v = self.module.avg
        self._current_average = v

    def run_single(self):
        """
        Runs a single acquisition.
        """

        self.button_continuous.setEnabled(False)
        self.restart_averaging()
        self.module.setup()
        self.acquire_one_curve()
        self.button_continuous.setEnabled(True)

    def update_display(self):
        """
        Updates the curve and the number of averages. Framerate has a ceiling.
        """

        if not hasattr(self, '_lasttime') \
                or (time() - 1.0/self._display_max_frequency) > self._lasttime:
            self._lasttime = time()
            # convert data from W to dBm
            x = self.x_data
            y = self.module.data_to_dBm(self.y_data)
            self.curve.setData(x, y)
            if self.running:
                buttontext = 'Stop (%i' % self.current_average
                if self.current_average >= self.module.avg:
                    # shows a plus sign when number of averages is available
                    buttontext += '+)'
                else:
                    buttontext += ')'
                self.button_continuous.setText(buttontext)

    def acquire_one_curve(self):
        """
        Acquires only one curve.
        """

        # self.module.setup() ### For small BW, setup() then curve() takes

        # several seconds... In the mean time, no other event can be
        # treated. That's why the gui freezes...
        self.y_data = (self.current_average * self.y_data \
                       + self.module.curve()) / (self.current_average + 1)
        self.current_average += 1
        self.update_display()
        if self.running:
            self.module.setup()

    def run_continuous(self):
        """
        Launches a continuous acquisition (part of the public interface).
        """

        self.running = True
        self.button_single.setEnabled(False)
        self.button_continuous.setText("Stop")
        self.restart_averaging()
        self.module.setup()
        self.timer.setInterval(self.module.duration*1000)
        self.timer.start()

    def stop(self):
        """
        Stops the current continuous acquisition (part of the public interface).
        """
        self.timer.stop()
        self.button_continuous.setText("Run continuous")
        self.running = False
        self.button_single.setEnabled(True)

    def run_continuous_clicked(self):
        """
        Toggles the run continuous button and performs the required action.
        """

        if self.running:
            self.stop()
        else:
            self.run_continuous()

    def restart_averaging(self):
        """
        Restarts the curve averaging.
        """
        self.x_data = self.module.freqs()
        self.y_data = np.zeros(len(self.x_data))
        self.current_average = 0


class RedPitayaGui(RedPitaya):
    """
    Widget for the main RedPitayaGui window.
    """

    def __init__(self, console_ns={'dummy':'dummy'}, *args, **kwds):
        super(RedPitayaGui, self).__init__(*args, **kwds)
        self.console_namespace = console_ns
        self.setup_gui()

<<<<<<< HEAD
    def setup_gui(self, CreatPyrpl=False):
        if CreatPyrpl:
            self.console_namespace={'dummy':'dummy'}
        self.na_widget = NaGui(parent=None, module=self.na)
        self.scope_widget = ScopeWidget(parent=None, module=self.scope, namespace=self.console_namespace)
        #self.scope_widget = ScopeWidget(parent=None, module=self.scope)
        self.all_asg_widget = AllAsgGui(parent=None, rp=self)
        self.sa_widget = SpecAnGui(parent=None, module=self.spec_an)
=======
    def add_dock_widget(self, widget, name):
        dock_widget = QtGui.QDockWidget(name)
        dock_widget.setObjectName(name)
        dock_widget.setFeatures(
            QtGui.QDockWidget.DockWidgetFloatable |
            QtGui.QDockWidget.DockWidgetMovable |
            QtGui.QDockWidget.DockWidgetVerticalTitleBar)
        self.dock_widgets[name] = dock_widget
        dock_widget.setWidget(widget)
        self.main_window.addDockWidget(QtCore.Qt.TopDockWidgetArea,
                                       dock_widget)
        if self.last_docked is not None:
            self.main_window.tabifyDockWidget(self.last_docked, dock_widget)
        self.last_docked = dock_widget

    def setup_gui(self):
        self.all_gui_modules = []
        self.na_widget = NaGui(name="na",
                               rp=self,
                               parent=None,
                               module=self.na)
        from pyrpl.gui.iq_gui import AllIqWidgets
        self.iq_widget = AllIqWidgets(rp=self,
                                  parent=None)
        self.scope_widget = ScopeWidget(name="scope",
                                        rp=self,
                                        parent=None,
                                        module=self.scope)
        self.sa_widget = SpecAnGui(name="spec an",
                                   rp=self,
                                   parent=None,
                                   module=self.spec_an)
        self.scope_sa_widget = ScopeSaWidget(self.scope_widget, self.sa_widget)
        self.all_asg_widget = AllAsgGui(parent=None,
                                        rp=self)
        self.all_pid_widget = AllPidGui(parent=None,
                                        rp=self)

        self.dock_widgets = {}
        self.last_docked = None
        self.main_window = QtGui.QMainWindow()
        for widget, name in [(self.scope_sa_widget, "Scope/Spec. An."),
                             (self.all_asg_widget, "Asgs"),
                             (self.all_pid_widget, "Pids"),
                             (self.na_widget, "Na"),
                             (self.iq_widget, "Iq")]:
            self.add_dock_widget(widget, name)
        self.main_window.setDockNestingEnabled(True)  # DockWidgets can be
        # stacked with one below the other one in the same column
        self.dock_widgets["Scope/Spec. An."].raise_()  # select first tab
>>>>>>> refs/remotes/origin/master

        """
        self.tab_widget = QtGui.QTabWidget()
        self.tab_widget.addTab(self.scope_widget, "Scope")
        self.tab_widget.addTab(self.all_asg_widget, "Asg")
        self.tab_widget.addTab(self.na_widget, "NA")
        self.tab_widget.addTab(self.sa_widget, "Spec. An.")
        self.custom_gui_setup()

        self.customize_scope()
        self.customize_na()
        self.custom_setup()
        """

    def gui(self, runcontinuous=True):
        """
        Opens the graphical user interface.
        """
        self.gui_timer = QtCore.QTimer()

        self.main_window.show()
        if runcontinuous:
            self.scope_widget.run_continuous()
        sys.exit(APP.exec_())

    def stop_all_timers(self):
        for tabnr in range(self.tab_widget.count()):
            try:
                self.tab_widget.widget(tabnr).stop_all_timers()
            except AttributeError:
                pass

    def custom_gui_setup(self):
        """
        Convenience hook for user functionality upon subclassing RedPitayaGui
        Returns
        -------
        """
        pass

    def customize_scope(self):
        """
        Convenience hook for user functionality upon subclassing RedPitayaGui
        Returns
        -------

        """
        pass

    def customize_na(self):
        """
        Convenience hook for user functionality upon subclassing RedPitayaGui
        Returns
        -------

        """
        pass

    def custom_setup(self):
        """
        Convenience hook for user functionality upon subclassing RedPitayaGui
        Returns
        -------

        """
        pass

    @property
    def window_position(self):
        xy = self.main_window.pos()
        x = xy.x()
        y = xy.y()
        dxdy = self.main_window.size()
        dx = dxdy.width()
        dy = dxdy.height()
        return [x, y, dx, dy]

    @window_position.setter
    def window_position(self, coords):
        self.main_window.move(coords[0], coords[1])
        self.main_window.resize(coords[2], coords[3])


class UserModule(ModuleWidget):
    """
    Subclass this to make your own modules.
    property_names is a list of properties to be created.
    Make sure a default value is given to the class (e.g. length = 0.01 in
    the class declaration.)

    autosave is the list of properties that need to be monitored

    overwrite init_gui for custom gui construction
    """

    property_names = ["dummy_example"]
    autosave = []
    dummy_example = 3.0

    def __init__(self, pyrpl, name):
        self.rp = pyrpl.rp
        self.pyrpl = pyrpl
        super(UserModule, self).__init__(rp=pyrpl.rp, name=name)
        self.rp.add_dock_widget(self, name)
        pyrpl.register_persistent_properties(self, self.name, self.autosave)