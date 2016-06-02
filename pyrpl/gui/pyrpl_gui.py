from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import NotReadyError
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import numpy as np



APP = QtGui.QApplication.instance()
if APP is None:
    APP = QtGui.QApplication(["pyrpl_gui"])

def property_factory(module_widget, prop):
    if hasattr(module_widget.module, prop + 's'):
        new_prop = ComboProperty(prop, module_widget)
    elif hasattr(module_widget.module, prop[:-1] + 's'): # for instance inputs for input1
        new_prop = ComboProperty(prop, module_widget, prop[:-1] + 's')
    elif isinstance(getattr(module_widget.module, prop), bool):
        new_prop = BoolProperty(prop, module_widget)
    else:
        new_prop = NumberProperty(prop, module_widget)
    return new_prop

class BaseProperty(object):
    def __init__(self, name, module_widget):
        self.module_widget = module_widget
        self.name = name
        self.layout_v = QtGui.QVBoxLayout()
        self.label = QtGui.QLabel(name)
        self.layout_v.addWidget(self.label)
        self.module = self.module_widget.module
        self.set_widget()
        self.layout_v.addWidget(self.widget)
        self.module_widget.property_layout.addLayout(self.layout_v)
        self.module_widget.property_watch_timer.timeout.\
                                connect(self.update_widget)
    
    def update_widget(self):
        self.widget.blockSignals(True)
        self.update()
        self.widget.blockSignals(False)

class NumberProperty(BaseProperty):
    def set_widget(self):
        self.widget = QtGui.QDoubleSpinBox()
        self.widget.setDecimals(4)
        self.widget.setSingleStep(0.01)
        self.widget.valueChanged.connect(self.write)
    
    def write(self):
        setattr(self.module, self.name, self.widget.value())
        self.module_widget.property_changed.emit()

    def update(self):
        self.widget.setValue(float(getattr(self.module, self.name)))
        
            
class ComboProperty(BaseProperty):
    def __init__(self, name, module_widget, defaults=None):
        if defaults is not None:
            self.defaults = defaults
        else:
            self.defaults = name + 's'
        super(ComboProperty, self).__init__(name, module_widget)

    def set_widget(self):
        self.widget = QtGui.QComboBox()
        self.widget.addItems(map(str, self.options))
        self.widget.currentIndexChanged.connect(self.write)
    
    @property
    def options(self):
        return getattr(self.module, self.defaults)
    
    def write(self):
        setattr(self.module, self.name, str(self.widget.currentText()))
        self.module_widget.property_changed.emit()
        
    def update(self):
        index = self.options.index(getattr(self.module, self.name))
        self.widget.setCurrentIndex(index)
    
class BoolProperty(BaseProperty):
    def set_widget(self):
        self.widget = QtGui.QCheckBox()
        self.widget.stateChanged.connect(self.write)
    
    def write(self):
        setattr(self.module, self.name, self.widget.checkState()==2)
        self.module_widget.property_changed.emit()

    def update(self):
        self.widget.setCheckState(getattr(self.module, self.name)*2)

class ModuleWidget(QtGui.QWidget):
    property_changed = QtCore.pyqtSignal()
    property_names = []
    def __init__(self, parent=None, module=None):
        super(ModuleWidget, self).__init__(parent)
        self.module = module
        self.init_gui()
        self.update_properties()

    def init_property_layout(self):
        self.property_watch_timer = QtCore.QTimer()
        self.property_watch_timer.setInterval(1000)
        self.property_watch_timer.start()

        self.property_layout = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.property_layout)
        self.properties = []

        for prop_name in self.property_names:
            prop = property_factory(self, prop_name)
            self.properties.append(prop)

    def init_gui(self):
        raise NotImplementedError()

    def update_properties(self):
        for prop in self.properties:
            prop.update_widget()

class ScopeWidget(ModuleWidget):
    property_names = ["input1",
                      "input2",
                      "duration",
                      "average",
                      "trigger_source",
                      "threshold_ch1",
                      "threshold_ch2"]

    def display_channel(self, ch):
        try:
           self.curves[ch-1].setData(self.module.times,
                                     self.module.curve(ch))
        except NotReadyError:
            pass
        
    def display_curves(self):
        for i in (1,2):
            if self.cb_ch[i-1].checkState()==2:
                self.display_channel(i)
                self.curves[i-1].setVisible(True)
            else:
                self.curves[i-1].setVisible(False)

    def run_single(self):
        self.module.setup()
        self.plot_item.enableAutoRange('xy', True)
        self.display_curves()


    def do_run_continuous(self):
        if self.module.curve_ready():
            #print "before"
            self.display_curves()
            #print "after"
            if self.first_shot_of_continuous:
                self.first_shot_of_continuous = False
                self.plot_item.enableAutoRange('xy', False)
            #print "before setup"
            self.module.setup()
            #print "after setup"
        self.timer.start()

    def run_continuous(self):
        if str(self.button_continuous.text())\
                   =="Run continuous":
            self.button_continuous.setText("Stop")
            self.button_single.setEnabled(False)
            self.module.setup()
            self.plot_item.enableAutoRange('xy', True)
            self.first_shot_of_continuous = True
            self.timer.start()
        else:
            self.button_continuous.setText("Run continuous")
            self.timer.stop()
            self.button_single.setEnabled(True)

    def init_gui(self):
        self.ch_col = ('blue', 'red')
        self.main_layout = QtGui.QVBoxLayout()
        self.init_property_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Scope")
        self.win = pg.GraphicsWindow(title="Scope")
        self.plot_item = self.win.addPlot(title="Scope")
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.curves = [self.plot_item.plot(pen=color[0]) \
                       for color in self.ch_col]
        self.main_layout.addWidget(self.win)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.main_layout.addLayout(self.button_layout)
        self.cb_ch = []
        for i in (1,2):
            self.cb_ch.append(QtGui.QCheckBox("Channel "+str(i)))
            self.button_layout.addWidget(self.cb_ch[-1])

        self.button_single.clicked.connect(self.run_single)
        self.button_continuous.clicked.connect(self.run_continuous)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(10)
        self.timer.setSingleShot(True)

        self.timer.timeout.connect(self.do_run_continuous)

        for cb, col in zip(self.cb_ch, self.ch_col):
            cb.setCheckState(2)
            cb.setStyleSheet('color: ' + col)
        for cb in self.cb_ch:
            cb.stateChanged.connect(self.display_curves)

        

class AsgGui(ModuleWidget):
    property_names = ["waveform", "scale", "offset", "frequency", "trigger_source"]
    def init_gui(self):
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
        for prop in self.properties:
            if prop.name == "frequency":
                break
        freq_spin_box = prop.widget
        freq_spin_box.setDecimals(1)
        freq_spin_box.setMaximum(100e6)
        freq_spin_box.setMinimum(-100e6)
        freq_spin_box.setSingleStep(100)
        self.property_changed.connect(self.module.setup)

class AllAsgGui(QtGui.QWidget):
    def __init__(self, parent=None, rp=None):
        super(AllAsgGui, self).__init__(parent)
        self.rp = rp
        self.asg_widgets = []
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)
        nr = 1
        self.layout.setAlignment(QtCore.Qt.AlignTop)

        while hasattr(self.rp, "asg" + str(nr)):
            widget = AsgGui(parent=None,
                    module=getattr(self.rp, "asg" + str(nr)))
            self.asg_widgets.append(widget)
            self.layout.addWidget(widget)
            nr+=1
            self.layout.setStretchFactor(widget, 0)


class NaGui(ModuleWidget):
    property_names = ["input1",
                      "input2",
                      "duration",
                      "average",
                      "trigger_source",
                      "threshold_ch1",
                      "threshold_ch2"]


    def display_channel(self, ch):
        try:
            self.curves[ch - 1].setData(self.module.times,
                                        self.module.curve(ch))
        except NotReadyError:
            pass


    def display_curves(self):
        for i in (1, 2):
            if self.cb_ch[i - 1].checkState() == 2:
                self.display_channel(i)
                self.curves[i - 1].setVisible(True)
            else:
                self.curves[i - 1].setVisible(False)


    def run_single(self):
        self.module.setup()
        self.plot_item.enableAutoRange('xy', True)
        self.display_curves()


    def do_run_continuous(self):
        if self.module.curve_ready():
            # print "before"
            self.display_curves()
            # print "after"
            if self.first_shot_of_continuous:
                self.first_shot_of_continuous = False
                self.plot_item.enableAutoRange('xy', False)
            # print "before setup"
            self.module.setup()
            # print "after setup"
        self.timer.start()


    def run_continuous(self):
        if str(self.button_continuous.text()) \
                == "Run continuous":
            self.button_continuous.setText("Stop")
            self.button_single.setEnabled(False)
            self.module.setup()
            self.plot_item.enableAutoRange('xy', True)
            self.first_shot_of_continuous = True
            self.timer.start()
        else:
            self.button_continuous.setText("Run continuous")
            self.timer.stop()
            self.button_single.setEnabled(True)


    def init_gui(self):
        self.ch_col = ('blue', 'red')
        self.main_layout = QtGui.QVBoxLayout()
        self.init_property_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Scope")
        self.win = pg.GraphicsWindow(title="Scope")
        self.plot_item = self.win.addPlot(title="Scope")
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.curves = [self.plot_item.plot(pen=color[0]) \
                       for color in self.ch_col]
        self.main_layout.addWidget(self.win)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.main_layout.addLayout(self.button_layout)
        self.cb_ch = []
        for i in (1, 2):
            self.cb_ch.append(QtGui.QCheckBox("Channel " + str(i)))
            self.button_layout.addWidget(self.cb_ch[-1])

        self.button_single.clicked.connect(self.run_single)
        self.button_continuous.clicked.connect(self.run_continuous)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(10)
        self.timer.setSingleShot(True)

        self.timer.timeout.connect(self.do_run_continuous)

        for cb, col in zip(self.cb_ch, self.ch_col):
            cb.setCheckState(2)
            cb.setStyleSheet('color: ' + col)
        for cb in self.cb_ch:
            cb.stateChanged.connect(self.display_curves)


class RedPitayaGui(RedPitaya):
    def gui(self):
        self.gui_timer = QtCore.QTimer()
        self.tab_widget = QtGui.QTabWidget()
        self.scope_widget = ScopeWidget(parent=None, module=self.scope)
        self.tab_widget.addTab(self.scope_widget, "Scope")
        self.all_asg_widget = AllAsgGui(parent=None, rp=self)
        self.tab_widget.addTab(self.all_asg_widget, "Asg")
        self.tab_widget.show()

        










