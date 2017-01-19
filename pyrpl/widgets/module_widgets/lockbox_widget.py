"""
The lockbox widget is composed of all the submodules widgets
"""

from .base_module_widget import ModuleWidget

from PyQt4 import QtCore, QtGui
import pyqtgraph as pg

import numpy as np

APP = QtGui.QApplication.instance()


class AnalogTfDialog(QtGui.QDialog):
    def __init__(self, parent):
        super(AnalogTfDialog, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        self.setWindowTitle("Analog transfer function for output %s" % self.module.name)
        self.lay_v = QtGui.QVBoxLayout(self)
        self.lay_h = QtGui.QHBoxLayout()
        self.ok = QtGui.QPushButton('Ok')
        self.lay_h.addWidget(self.ok)
        self.ok.clicked.connect(self.validate)
        self.cancel = QtGui.QPushButton('Cancel')
        self.lay_h.addWidget(self.cancel)
        self.group = QtGui.QButtonGroup()
        self.flat = QtGui.QRadioButton("Flat response")
        self.filter = QtGui.QRadioButton('Analog filter (in "assisted design section")')
        self.curve = QtGui.QRadioButton("User defined curve")
        self.group.addButton(self.flat)
        self.group.addButton(self.filter)
        self.group.addButton(self.curve)

        self.lay_v.addWidget(self.flat)
        self.lay_v.addWidget(self.filter)
        self.lay_v.addWidget(self.curve)
        self.label = QtGui.QLabel("Curve #")
        self.line = QtGui.QLineEdit("coucou")

        self.lay_line = QtGui.QHBoxLayout()
        self.lay_v.addLayout(self.lay_line)
        self.lay_v.addWidget(self.line)
        self.lay_line.addStretch(1)
        self.lay_line.addWidget(self.label)
        self.lay_line.addWidget(self.line, stretch=10)
        self.lay_v.addSpacing(20)
        self.lay_v.addLayout(self.lay_h)
        self.curve.toggled.connect(self.change_visibility)
        {'flat':self.flat, 'filter':self.filter, 'curve':self.curve}[self.module.tf_type].setChecked(True)

        self.line.setText(str(self.module.tf_curve))
        self.line.textEdited.connect(lambda: self.line.setStyleSheet(""))
        self.cancel.clicked.connect(self.reject)
        self.curve_id = None
        self.res = None


    def change_visibility(self, checked):
        print(checked)
        for widget in self.label, self.line:
            widget.setEnabled(checked)

    def validate(self):
        self.line.setStyleSheet('')
        if self.flat.isChecked():
            self.res = "flat"
            self.accept()
        if self.filter.isChecked():
            self.res = 'filter'
            self.accept()
        if self.curve.isChecked():
            try:
                curve_id = int(str(self.line.text()))
            except:
                self.line.setStyleSheet('background-color:red;')
            else:
                self.res = 'curve'
                self.curve_id = curve_id
                self.accept()

    def get_type_number(self):
        accept = self.exec_()
        return accept, self.res, self.curve_id


class AnalogTfSpec(QtGui.QWidget):
    """
    A button + label that allows to display and change the transfer function specification
    """
    def __init__(self, parent):
        super(AnalogTfSpec, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        self.layout = QtGui.QVBoxLayout(self)
        self.label = QtGui.QLabel("Analog t. f.")
        self.layout.addWidget(self.label)
        self.button = QtGui.QPushButton('Change...')
        self.layout.addWidget(self.button)
        self.button.clicked.connect(self.change)
        self.dialog = AnalogTfDialog(self)
        self.layout.setContentsMargins(0,0,0,0)
        self.change_analog_tf()

    def change(self, ev):
        accept, typ, number = self.dialog.get_type_number()
        if accept:
            if typ=='curve':
                self.module.tf_curve = number
            self.module.tf_type = typ

    def change_analog_tf(self):
        txt = self.module.tf_type
        if self.module.tf_type=='curve':
            txt += ' #' + str(self.module.tf_curve)
        self.button.setText(txt)


class MainOutputProperties(QtGui.QGroupBox):
    def __init__(self, parent):
        super(MainOutputProperties, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        aws = self.parent.attribute_widgets
        self.layout = QtGui.QHBoxLayout(self)
        self.v1 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v1)
        self.v2 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v2)
        self.v1.addWidget(aws["name"])
        self.v1.addWidget(aws['dc_gain'])
        aws['dc_gain'].set_log_increment()
        self.v2.addWidget(aws["output_channel"])
        # self.v2.addWidget(aws["tf_type"])
        self.button_tf = AnalogTfSpec(self)
        self.v2.addWidget(self.button_tf)

#        aws['tf_curve'].hide()
        self.setTitle('main attributes')
        for v in self.v1, self.v2:
            v.setSpacing(9)

    def change_analog_tf(self):
        self.button_tf.change_analog_tf()


class SweepOutputProperties(QtGui.QGroupBox):
    def __init__(self, parent):
        super(SweepOutputProperties, self).__init__(parent)
        self.parent = parent
        aws = self.parent.attribute_widgets
        self.layout = QtGui.QHBoxLayout(self)
        self.v1 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v1)
        self.v2 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v2)
        self.v1.addWidget(aws["sweep_frequency"])
        self.v1.addWidget(aws['sweep_amplitude'])
        self.v2.addWidget(aws["sweep_offset"])
        self.v2.addWidget(aws["sweep_waveform"])
        aws['is_sweepable'].hide()
        self.setTitle("sweep attributes")


class WidgetManual(QtGui.QWidget):
    def __init__(self, parent):
        super(WidgetManual, self).__init__(parent)
        self.parent = parent
        self.layout = QtGui.QVBoxLayout(self)
        self.p = parent.parent.attribute_widgets["p"]
        self.i = parent.parent.attribute_widgets["i"]
        self.p.label.setText('p [1] ')
        self.i.label.setText('i [Hz]')
        self.p.label.setFixedWidth(24)
        self.i.label.setFixedWidth(24)
        # self.p.adjustSize()
        # self.i.adjustSize()

        for prop in self.p, self.i:
            prop.widget.set_log_increment()

        self.p.set_horizontal()
        self.i.set_horizontal()
        self.layout.addWidget(self.p)
        self.layout.addWidget(self.i)
        # self.i.label.setMinimumWidth(6)

class WidgetAssisted(QtGui.QWidget):
    def __init__(self, parent):
        super(WidgetAssisted, self).__init__(parent)
        self.parent = parent
        self.layout = QtGui.QHBoxLayout(self)
        self.v1 = QtGui.QVBoxLayout()
        self.v2 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v1)
        self.layout.addLayout(self.v2)
        self.desired = parent.parent.attribute_widgets["unity_gain_desired"]
        self.desired.set_log_increment()
        self.analog_filter = parent.parent.attribute_widgets["analog_filter"]
        #self.analog_filter.set_horizontal()
        # self.analog_filter.layout_v.setSpacing(0)
        # self.analog_filter.layout_v.setContentsMargins(0, 0, 0, 0)
        self.analog_filter.set_max_cols(2)
        self.v1.addWidget(self.desired)
        self.v2.addWidget(self.analog_filter)

class PidProperties(QtGui.QGroupBox):
    def __init__(self, parent):
        super(PidProperties, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        aws = self.parent.attribute_widgets
        self.layout = QtGui.QHBoxLayout(self)
        self.v1 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v1)
        self.v2 = QtGui.QVBoxLayout()
        self.layout.addLayout(self.v2)

        self.radio_group = QtGui.QButtonGroup()
        self.manual = QtGui.QRadioButton('manual design')
        self.assisted = QtGui.QRadioButton('assisted design')
        self.radio_group.addButton(self.manual)
        self.radio_group.addButton(self.assisted)
        self.assisted.clicked.connect(self.toggle_mode)
        self.manual.clicked.connect(self.toggle_mode)

        self.manual_widget = WidgetManual(self)
        self.v1.addWidget(self.manual)
        self.v1.addWidget(self.manual_widget)
        # self.col3.addWidget(aws["tf_filter"])

        self.assisted_widget = WidgetAssisted(self)
        self.v2.insertWidget(0, self.assisted)
        self.v2.addWidget(self.assisted_widget)
        self.v2.addStretch(5)

        self.setTitle("Pid control")

        for v in (self.v1, self.v2, self.layout):
            v.setSpacing(0)
            v.setContentsMargins(5, 1, 0, 0)

    def toggle_mode(self): # button clicked
        if self.manual.isChecked():
            self.module.assisted_design = False
        else:
            self.module.assisted_design = True

    def set_assisted(self):
        self.manual_widget.setEnabled(False)
        self.assisted_widget.setEnabled(True)

    def set_manual(self):
        self.manual_widget.setEnabled(True)
        self.assisted_widget.setEnabled(False)

class PostFiltering(QtGui.QGroupBox):
    def __init__(self, parent):
        super(PostFiltering, self).__init__(parent)
        self.parent = parent
        aws = self.parent.attribute_widgets
        self.layout = QtGui.QVBoxLayout(self)

        aws = self.parent.attribute_widgets
        self.layout.addWidget(aws["additional_filter"])

        self.mod_layout = QtGui.QHBoxLayout()
        self.mod_layout.addWidget(aws["extra_module"])
        self.mod_layout.addWidget(aws["extra_module_state"])
        self.layout.addLayout(self.mod_layout)
        self.layout.setSpacing(12)

        self.setTitle("post filtering")


class OutputSignalWidget(ModuleWidget):
    @property
    def name(self):
        return self.module.name

    @name.setter
    def name(self, value):
        return value # only way to modify widget name is to change output.display_name

    def change_analog_tf(self):
        self.main_props.change_analog_tf()

    def set_assisted_design(self, val):
        """
        Disable the corresponding buttons in the pid property section.
        """
        self.pid_props.blockSignals(True)
        self.pid_props.manual.setChecked(not val)
        self.pid_props.assisted.setChecked(val)
        self.pid_props.blockSignals(False)
        {True:self.pid_props.set_assisted, False:self.pid_props.set_manual}[val]()

    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.init_attribute_layout()
        for widget in self.attribute_widgets.values():
            self.main_layout.removeWidget(widget)
        self.upper_layout = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.upper_layout)
        self.col1 = QtGui.QVBoxLayout()
        self.col2 = QtGui.QVBoxLayout()
        self.col3 = QtGui.QVBoxLayout()
        self.col4 = QtGui.QVBoxLayout()
        self.upper_layout.addStretch(1)
        self.upper_layout.addLayout(self.col1)
        self.upper_layout.addStretch(1)
        self.upper_layout.addLayout(self.col2)
        self.upper_layout.addStretch(1)
        self.upper_layout.addLayout(self.col3)
        self.upper_layout.addStretch(1)
        self.upper_layout.addLayout(self.col4)
        self.upper_layout.addStretch(1)

        aws = self.attribute_widgets
        self.main_props = MainOutputProperties(self)
        self.col1.addWidget(self.main_props)
        self.col1.addStretch(5)

        self.sweep_props = SweepOutputProperties(self)
        self.col2.addWidget(self.sweep_props)
        self.col2.addStretch(5)

        self.pid_props = PidProperties(self)
        self.set_assisted_design(self.module.assisted_design)
        self.col3.addWidget(self.pid_props)

        self.col3.addStretch(5)

        self.post_props = PostFiltering(self)
        self.col4.addWidget(self.post_props)

        self.col4.addStretch(5)

        self.win = pg.GraphicsWindow(title="Amplitude")
        self.win_phase = pg.GraphicsWindow(title="Phase")
        self.plot_item = self.win.addPlot(title="Magnitude (dB)")
        self.plot_item_phase = self.win_phase.addPlot(title="Phase (deg)")
        self.plot_item.showGrid(y=True, x=True, alpha=1.)
        self.plot_item_phase.showGrid(y=True, x=True, alpha=1.)

        self.plot_item_phase.setXLink(self.plot_item)

        self.curve = self.plot_item.plot(pen='y')
        self.curve_phase = self.plot_item_phase.plot(pen=None, symbol='o', symbolSize=1)

        self.plot_item.setLogMode(x=True, y=True)
        self.plot_item_phase.setLogMode(x=True, y=None)
        self.curve.setLogMode(xMode=True, yMode=True)
        self.curve_phase.setLogMode(xMode=True, yMode=None)

        self.main_layout.addWidget(self.win)
        self.main_layout.addWidget(self.win_phase)
        self.update_transfer_function()

    def update_transfer_function(self):
        """
        Updates the transfer function curve of the output.
        """
        freqs = self.module.tf_freqs()
        curve = self.module.transfer_function(freqs)
        abs_curve = abs(curve)
        if(max(abs_curve)>0): # python 2 crashes when plotting zeros in log_mode
            self.curve.setData(freqs, abs_curve)
            self.curve_phase.setData(freqs, 180./np.pi*np.angle(curve))


class LockboxInputWidget(ModuleWidget):
    """
    A widget to represent a single lockbox input
    """
    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout(self)
        self.init_attribute_layout()

        self.win = pg.GraphicsWindow(title="Expected signal")
        self.plot_item = self.win.addPlot(title='Expected ' + self.module.name)
        self.plot_item.showGrid(y=True, x=True, alpha=1.)
        self.curve = self.plot_item.plot(pen='y')
        self.curve_slope = self.plot_item.plot(pen=pg.mkPen('b', width=5))
        self.symbol = self.plot_item.plot(pen='b', symbol='o')
        self.main_layout.addWidget(self.win)

        self.button_calibrate = QtGui.QPushButton('Calibrate')

        self.main_layout.addWidget(self.button_calibrate)
        self.button_calibrate.clicked.connect(self.module.calibrate)

    def hide_lock(self):
        self.curve_slope.setData([], [])
        self.symbol.setData([], [])
        self.plot_item.enableAutoRange(enable=True)

    def show_lock(self, input, variable_value):
        signal = self.module.expected_signal(variable_value)
        slope = self.module.expected_slope(variable_value)
        dx = 1
        self.plot_item.enableAutoRange(enable=False)
        self.curve_slope.setData([variable_value - dx, variable_value + dx],
                                 [signal - slope * dx, signal + slope*dx])
        self.symbol.setData([variable_value], [signal])

    def show_graph(self, x, y):
        """
        x, y are two 1D arrays.
        """
        self.curve.setData(x, y)

class InputsWidget(QtGui.QWidget):
    """
    A widget to represent all input signals on the same tab
    """
    name = 'inputs'
    def __init__(self, all_sig_widget):
        self.all_sig_widget = all_sig_widget
        self.lb_widget = self.all_sig_widget.lb_widget
        super(InputsWidget, self).__init__(all_sig_widget)
        self.layout = QtGui.QHBoxLayout(self)
        self.input_widgets = []
        #self.layout.addStretch(1)
        for signal in self.lb_widget.module.inputs:
            self.add_input(signal)
        #self.layout.addStretch(1)

    def remove_input(self, input):
        if input.widget in self.input_widgets:
            input.widget.hide()
            self.input_widgets.remove(input.widget)
            input.widget.deleteLater()

    def add_input(self, input):
        widget = input.create_widget()
        self.input_widgets.append(widget)
        self.layout.addWidget(widget, stretch=3)


class PlusTab(QtGui.QWidget):
    name = '+'


class MyTabBar(QtGui.QTabBar):
    def tabSizeHint(self, index):
        """
        Tab '+' and 'inputs' are smaller since they don't have a close button
        """
        size = super(MyTabBar, self).tabSizeHint(index)
        #if index==0 or index==self.parent().count() - 1:
        #    return QtCore.QSize(size.width() - 15, size.height())
        #else:
        return size

class AllSignalsWidget(QtGui.QTabWidget):
    """
    A tab widget combining all inputs and outputs of the lockbox
    """
    def __init__(self, lockbox_widget):
        super(AllSignalsWidget, self).__init__()
        self.tab_bar = MyTabBar()
        self.setTabBar(self.tab_bar)
        self.setTabsClosable(True)
        self.tabBar().setSelectionBehaviorOnRemove(QtGui.QTabBar.SelectLeftTab) # otherwise + tab could be selected by
        # removing previous tab
        self.output_widgets = []
        self.lb_widget = lockbox_widget
        self.inputs_widget = InputsWidget(self)
        self.addTab(self.inputs_widget, "inputs")
        self.tabBar().tabButton(0, QtGui.QTabBar.RightSide).resize(0, 0) # hide "close" for "inputs" tab
        self.tab_plus = PlusTab()  # dummy widget that will never be displayed
        self.addTab(self.tab_plus, "+")
        self.tabBar().tabButton(self.count() - 1, QtGui.QTabBar.RightSide).resize(0, 0)  # hide "close" for "+" tab
        for signal in self.lb_widget.module.outputs:
            self.add_output(signal)
        self.currentChanged.connect(self.tab_changed)
        self.tabCloseRequested.connect(self.close_tab)
        self.update_output_names()

    def tab_changed(self, index):
        if index==self.count()-1: # tab "+" clicked
            self.lb_widget.module.add_output()
            self.setCurrentIndex(self.count()-2) # bring created output tab on top

    def close_tab(self, index):
        lockbox = self.lb_widget.module
        lockbox.remove_output(lockbox.outputs[index - 1])

    ## Output Management
    def add_output(self, signal):
        """
        signal is an instance of OutputSignal
        """
        widget = signal.create_widget()
        self.output_widgets.append(widget)
        self.insertTab(self.count() - 1, widget, widget.name)

    def remove_output(self, output):
        tab_nr = self.output_widgets.index(output.widget) + 1  # count "inputs" tab
        if output.widget in self.output_widgets:
            output.widget.hide()
            self.output_widgets.remove(output.widget)
            self.removeTab(tab_nr)
            output.widget.deleteLater()

    def update_output_names(self):
        for index in range(self.count()):
            widget = self.widget(index)
            self.setTabText(index, widget.name)

    ## Input Management
    def add_input(self, input):
        self.inputs_widget.add_input(input)

    def remove_input(self, input):
        self.inputs_widget.remove_input(input)

class MyCloseButton(QtGui.QPushButton):
    def __init__(self, parent=None):
        super(MyCloseButton, self).__init__(parent)
        style = APP.style()
        close_icon = style.standardIcon(QtGui.QStyle.SP_TitleBarCloseButton)
        self.setIcon(close_icon)
        self.setFixedHeight(16)
        self.setFixedWidth(16)


class LockboxStageWidget(ModuleWidget):
    """
    A widget representing a single lockbox stage
    """
    @property
    def name(self):
        return self.module.name

    @name.setter
    def name(self, value):
        return value  # only way to modify widget name is to change output.display_name

    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout(self)
        self.init_attribute_layout()
        for name, attr in self.attribute_widgets.items():
            self.attribute_layout.removeWidget(attr)
        self.lay_h1 = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.lay_h1)
        self.lay_v1 = QtGui.QVBoxLayout()
        self.lay_h1.addLayout(self.lay_v1)
        self.lay_v2 = QtGui.QVBoxLayout()
        self.lay_h1.addLayout(self.lay_v2)
        aws = self.attribute_widgets
        self.lay_v1.addWidget(aws['name'])
        self.lay_v1.addWidget(aws['input'])
        self.lay_v2.addWidget(aws['duration'])
        self.lay_v2.addWidget(aws['variable_value'])
        self.main_layout.addWidget(aws['output_on'])

        self.main_layout.addWidget(aws['function_call'])

        self.button_goto = QtGui.QPushButton('Goto stage')
        self.button_goto.clicked.connect(self.module.setup)
        self.main_layout.addWidget(self.button_goto)

    def create_title_bar(self):
        super(LockboxStageWidget, self).create_title_bar()
        self.close_button = MyCloseButton(self)
        self.close_button.clicked.connect(self.close)
        self.close_button.move(self.width() - self.close_button.width(), self.title_pos[1] + 8)

    def resizeEvent(self, evt):
        super(LockboxStageWidget, self).resizeEvent(evt)
        self.close_button.move(evt.size().width() - self.close_button.width(), self.title_pos[1])

    def close(self):
        self.module.parent.remove_stage(self.module)

    def show_lock(self):
        self.parent().parent().set_button_green(self.button_goto)



class LockboxSequenceWidget(ModuleWidget):
    """
    A widget to represent all lockbox stages
    """
    def init_gui(self):
        self.main_layout = QtGui.QHBoxLayout(self)
        self.init_attribute_layout() # eventhough, I don't think there's any attribute
        self.stage_widgets = []
        self.button_add = QtGui.QPushButton('+')
        self.button_add.setSizePolicy(QtGui.QSizePolicy.Fixed, QtGui.QSizePolicy.Expanding)
        self.button_add.setMinimumHeight(60)
        for stage in self.module.stages:
            self.add_stage(stage)
        self.button_add.clicked.connect(self.module.add_stage)
        self.main_layout.addWidget(self.button_add)
        self.main_layout.addStretch(2)

    def add_stage(self, stage):
        widget = stage.create_widget()
        self.stage_widgets.append(widget)
        self.main_layout.insertWidget(self.main_layout.indexOf(self.button_add), widget)
        return stage

    def remove_stage(self, stage):
        if stage.widget in self.stage_widgets:
            stage.widget.hide()
            self.stage_widgets.remove(stage.widget)
            self.main_layout.removeWidget(stage.widget)
            stage.widget.deleteLater()

    def update_stage_names(self):
        for widget in self.stage_widgets:
            widget.set_title(widget.name)


class LockboxWidget(ModuleWidget):
    """
    The LockboxWidget combines the lockbox submodules widget: model, inputs, outputs, lockbox_control
    """
    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.init_attribute_layout()
        self.button_lock = QtGui.QPushButton("Lock")
        self.button_unlock = QtGui.QPushButton("Unlock")
        self.button_green = self.button_unlock
        self.set_button_green(self.button_green)
        self.button_lock.clicked.connect(self.module.lock)
        self.attribute_layout.addWidget(self.button_lock)
        self.attribute_layout.addWidget(self.button_unlock)
        self.button_unlock.clicked.connect(self.module.unlock)
        self.button_sweep = QtGui.QPushButton("Sweep")
        self.button_sweep.clicked.connect(self.module.sweep)
        self.attribute_layout.addWidget(self.button_sweep)
        self.button_calibrate_all = QtGui.QPushButton("Calibrate all inputs")
        self.attribute_layout.addWidget(self.button_calibrate_all)
        self.button_calibrate_all.clicked.connect(self.module.calibrate_all)

        self.model_widget = self.module.model.create_widget()
        self.main_layout.addWidget(self.model_widget)
        self.all_sig_widget = AllSignalsWidget(self)
        self.main_layout.addWidget(self.all_sig_widget)
        self.sequence_widget = self.module.sequence.create_widget()
        self.main_layout.addWidget(self.sequence_widget)
        self.main_layout.addStretch(5)
        self.setLayout(self.main_layout)

    ## Input Management
    def add_input(self, input):
        """
        Adds an input to the widget
        """
        self.all_sig_widget.add_input(input)

    def remove_input(self, input):
        """
        Remove an input to the widget
        """
        self.all_sig_widget.remove_input(input)

    ## Output Management
    def update_output_names(self):
        """
        Refresh all output name tabs in the widget
        """
        self.all_sig_widget.update_output_names()

    def add_output(self, output):
        """
        Adds an output to the widget
        """
        self.all_sig_widget.add_output(output)

    def remove_output(self, output):
        """
        Removes an output to the widget
        """
        self.all_sig_widget.remove_output(output)

    ## Model management
    def change_model(self, model):
        """
        displays the new model
        """
        self.model_widget.hide()
        self.main_layout.removeWidget(self.model_widget)
        self.model_widget.deleteLater()
        widget = model.create_widget()
        self.model_widget = widget
        self.main_layout.insertWidget(1, widget)

    ## Sequence Management
    def add_stage(self, stage):
        """
        Adds a new stage to the widget
        """
        self.sequence_widget.add_stage(stage)

    def remove_stage(self, stage):
        """
        Removes a stage to the model
        """
        self.sequence_widget.remove_stage(stage)

    def set_state(self, val):
        if val=='unlock':
            self.set_button_green(self.button_unlock)
            self.hide_lock_points()
            return
        if val=='sweep':
            self.hide_lock_points()
            self.set_button_green(self.button_sweep)
            return
        index = self.module.stage_names.index(val)
        self.set_button_green(self.sequence_widget.stage_widgets[index].button_goto)
        self.show_lock(val)

    def set_button_green(self, button):
        """
        Only one colored button can exist at a time
        """
        self.button_green.setStyleSheet("")
        button.setStyleSheet("background-color:green")
        self.button_green = button

    def show_lock(self, stage):
        """
        The button of the stage widget becomes green, the expected signal graph of input show the lock point and slope.
        """
        self.hide_lock_points()
        if isinstance(stage, basestring):
            stage = self.module.get_stage(stage)
        if stage is not None:
            if stage.widget is not None:
                stage.widget.show_lock()
            input_widget = self.module.get_input(stage.input).widget
            if input_widget is not None:
                input_widget.show_lock(stage.input, stage.variable_value)

    def hide_lock_points(self):
        """
        make sure all input graphs are not displaying any setpoints and slopes
        """
        for input_widget in self.all_sig_widget.inputs_widget.input_widgets:
            input_widget.hide_lock()

