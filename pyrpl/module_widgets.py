"""
ModuleWidgets's hierarchy is parallel to that of Modules.
Each Module instance can have a widget created by calling create_widget.
To use a different class of Widget than the preset (for instance subclass it), the attribute ModuleClass.WidgetClass
can be changed before calling create_widget()
"""

from PyQt4 import QtCore, QtGui
from pyrpl import CurveDB
from collections import OrderedDict
import pyqtgraph as pg
from .redpitaya_modules import NotReadyError

class ModuleWidget(QtGui.QWidget):
    """
    Base class for a module Widget. In general, this is one of the Tab in the
    final RedPitayaGui object.
    """

    attribute_changed = QtCore.pyqtSignal()
    # register_names = [] # a list of all register name to expose in the gui
    curve_class = CurveDB # Change this to save the curve with a different system

    def __init__(self, name, module, parent=None):
        super(ModuleWidget, self).__init__(parent)
        #self.rp = rp
        self.module = module
        self.name = name
        self.attribute_widgets = OrderedDict()
        self.init_gui() # performs the automatic gui creation based on register_names
        self.update_attribute_widgets()
#        self.rp.all_gui_modules.append(self)

    # I don't see why it should be done at the gui level rather than module level. Let's remove it from here
    #def get_state(self):
    #    """returns a dictionary containing all properties listed in
    #    property_names."""
    #    #Not sure if we should also set the state of the underlying module

    #   dic = dict()
    #    for val in self.property_names:
    #        dic[val] = getattr(self.module, val)
    #    return dic

    #def set_state(self, dic):
    #    """Sets the state using a dictionary"""

    #    for key, val in dic.iteritems():
    #        setattr(self.module, key, val)
    #    self.module.setup()


    #def stop_all_timers(self):
    #    self.property_watch_timer.stop()
    #    try:
    #        self.timer.stop()
    #    except AttributeError:
    #        pass

    def init_attribute_layout(self):
        """
        Automatically creates the gui properties for the register_widgets in register_names.
        :return:
        """

        self.attribute_layout = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.attribute_layout)

        for attr_name in self.module.gui_attributes:
            widget = getattr(self.module.__class__, attr_name).create_widget(self.module)
            self.attribute_widgets[attr_name] = widget
            self.attribute_layout.addLayout(widget.layout_v)
            widget.value_changed.connect(self.attribute_changed)

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
        self.init_attribute_layout()

    def update_attribute_widgets(self):
        """
        Updates all register_widgets listed in self.register_widgets

        :return:
        """
        for reg in self.attribute_widgets.values():
            if not reg.editing():
                reg.update_widget()


class ScopeWidget(ModuleWidget):
    """
    Widget for scope
    """
    """
    register_names = ["input1",
                      "input2",
                      "duration",
                      "average",
                      "trigger_source",
                      "trigger_delay",
                      "threshold_ch1",
                      "threshold_ch2",
                      "curve_name"]
    """
    def init_gui(self):
        """
        sets up all the gui for the scope.
        """

        self.datas = [None, None]
        self.times = None
        self.ch_col = ('green', 'red')
        self.module.__dict__['curve_name'] = 'scope'
        self.main_layout = QtGui.QVBoxLayout()
        self.init_attribute_layout()
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
        self.attribute_layout.insertWidget(
            list(self.attribute_widgets.keys()).index("trigger_source"), self.rolling_group)
        self.checkbox_normal.clicked.connect(self.rolling_mode_toggled)
        self.checkbox_untrigged.clicked.connect(self.rolling_mode_toggled)
        #self.checkbox_normal.enabledChange.connect(self.rolling_mode_toggled)

        # minima maxima
        # for prop in (self.properties["threshold_ch1"],
        #            self.properties["threshold_ch2"]):
        #    spin_box = prop.widget
        #    spin_box.setDecimals(4)
        #    spin_box.setMaximum(1)
        #    spin_box.setMinimum(-1)
        #    spin_box.setSingleStep(0.01)

        #self.properties["curve_name"].acquisition_property = False

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
        if not self.rolling_mode: # otherwise, evrything is handled in check_for_curves
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

    def update_attribute_widgets(self):
        super(ScopeWidget, self).update_attribute_widgets()

        self.rolling_group.setEnabled(self.module.duration > 0.1)
        self.attribute_widgets['trigger_source'].widget.setEnabled(
            not self.rolling_mode)
        old = self.attribute_widgets['threshold_ch1'].widget.isEnabled()
        self.attribute_widgets['threshold_ch1'].widget.setEnabled(
            not self.rolling_mode)
        self.attribute_widgets['threshold_ch2'].widget.setEnabled(
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

class AsgWidget(ModuleWidget):
    def __init__(self, *args, **kwds):
        super(AsgWidget, self).__init__(*args, **kwds)
        self.attribute_widgets['trigger_source'].value_changed.connect(self.module.setup)


class IqWidget(ModuleWidget):
    """
    Widget for the IQ module
    """

    def init_gui(self):
        super(IqWidget, self).init_gui()
        ##Then remove properties from normal property layout
        ## We will make a more fancy one !


        for key, widget in self.attribute_widgets.items():
            layout = widget.layout_v
            self.attribute_layout.removeItem(widget.layout_v)
            """
            prop.the_widget = WidgetProp(prop.label, prop.widget)
            if key!='bandwidth':
                prop.the_widget.setMaximumWidth(120)
            """
            #self.scene.addWidget(prop.the_widget)

        self.attribute_widgets["bandwidth"].widget.set_max_cols(2)
        self.attribute_layout.addLayout(self.attribute_widgets["input"].layout_v)
        self.attribute_layout.addLayout(self.attribute_widgets["acbandwidth"].layout_v)
        self.attribute_layout.addLayout(self.attribute_widgets["frequency"].layout_v)
        self.attribute_widgets["frequency"].layout_v.addLayout(self.attribute_widgets["phase"].layout_v)
        #self.attribute_widgets["frequency"].widget.setMaximum(125e6/2)
        #self.attribute_widgets["frequency"].widget.step = 125e6/2**32
        #self.attribute_widgets["phase"].widget.setMaximum(360)
        #self.attribute_widgets["phase"].widget.step = 0.1
        self.attribute_layout.addLayout(self.attribute_widgets["bandwidth"].layout_v)
        self.attribute_layout.addLayout(self.attribute_widgets["quadrature_factor"].layout_v)
        self.attribute_layout.addLayout(self.attribute_widgets["gain"].layout_v)
        self.attribute_layout.addLayout(self.attribute_widgets["amplitude"].layout_v)
        self.attribute_layout.addLayout(self.attribute_widgets["output_signal"].layout_v)
        self.attribute_widgets["output_signal"].layout_v.addLayout(self.attribute_widgets["output_direct"].layout_v)

        property_acbw = self.attribute_widgets["acbandwidth"]


        #def update():
        #    """
        #    Sets the gui value from the current module value
#
#            :return:
#            """
#
#            index = list(property_acbw.options).index(int(getattr(property_acbw.module,
#                                                                      property_acbw.name)))
#            property_acbw.widget.setCurrentIndex(index)
#
#        property_acbw.update = update
