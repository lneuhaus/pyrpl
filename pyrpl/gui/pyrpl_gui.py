from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import NotReadyError
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import numpy as np


class BaseProperty(object):
    def __init__(self, name, scope_widget):
        self.scope_widget = scope_widget
        self.name = name
        self.layout_v = QtGui.QVBoxLayout()
        self.label = QtGui.QLabel(name)
        self.layout_v.addWidget(self.label)
        self.scope = self.scope_widget.rp.scope
        self.set_widget()
        self.layout_v.addWidget(self.widget)
        self.scope_widget.property_layout.addLayout(self.layout_v)
        self.scope_widget.property_watch_timer.timeout.\
                                connect(self.update_widget)
    
    def update_widget(self):
        self.widget.blockSignals(True)
        self.update()
        self.widget.blockSignals(False)

class NumberProperty(BaseProperty):
    def set_widget(self):
        self.widget = QtGui.QDoubleSpinBox()
        self.widget.valueChanged.connect(self.write)
    
    def write(self):
        setattr(self.scope, self.name, self.widget.value())
        
    def update(self):
        self.widget.setValue(float(getattr(self.scope, self.name)))
        
            
class ComboProperty(BaseProperty):
    def set_widget(self):
        self.widget = QtGui.QComboBox()
        self.widget.addItems(map(str, self.options))
        self.widget.currentIndexChanged.connect(self.write)
    
    @property
    def options(self):
        return getattr(self.scope, self.name + 's')
    
    def write(self):
        setattr(self.scope, self.name, str(self.widget.currentText()))
        
    def update(self):
        index = self.options.index(getattr(self.scope, self.name))
        self.widget.setCurrentIndex(index)
    
class BoolProperty(BaseProperty):
    def set_widget(self):
        self.widget = QtGui.QCheckBox()
        self.widget.stateChanged.connect(self.write)
    
    def write(self):
        setattr(self.scope, self.name, self.widget.checkState()==2)
        
    def update(self):
        self.widget.setCheckState(getattr(self.scope, self.name)*2)


class ScopeWidget(QtGui.QWidget):
    property_names = ["trigger_source",
                      "duration",
                      "threshold_ch1",
                      "threshold_ch2",  
                      "average"]
    def __init__(self, parent=None, redpitaya=None):
        super(ScopeWidget, self).__init__(parent)
        self.rp = redpitaya
        self.ch_col = ('blue', 'red')
        self.init_gui()
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
            
        self.update_properties()

    def display_channel(self, ch):
        try:
           self.curves[ch-1].setData(self.rp.scope.times, 
                                     self.rp.scope.curve(ch))
        except NotReadyError:
            pass
        
    def display_curves(self):
        for i in (1,2):
            if self.cb_ch[i-1].checkState()==2:
                self.display_channel(i)
                self.curves[i-1].setEnabled(True)
            else:
                self.curves[i-1].setEnabled(False)

    def run_single(self):
        self.rp.scope.setup()
        self.plot_item.enableAutoRange('xy', True)
        self.display_curves()


    def do_run_continuous(self):
        if self.rp.scope.curve_ready():
            #print "before"
            self.display_curves()
            #print "after"
            if self.first_shot_of_continuous:
                self.first_shot_of_continuous = False
                self.plot_item.enableAutoRange('xy', False)
            #print "before setup"
            self.rp.scope.setup()
            #print "after setup"
        self.timer.start()

    def run_continuous(self):
        if str(self.rp.scope_widget.button_continuous.text())\
                   =="Run continuous":
            self.button_continuous.setText("Stop")
            self.button_single.setEnabled(False)
            self.rp.scope.setup()
            self.plot_item.enableAutoRange('xy', True)
            self.first_shot_of_continuous = True
            self.timer.start()
        else:
            self.button_continuous.setText("Run continuous")
            self.timer.stop()
            self.button_single.setEnabled(True)

    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.init_property_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Redpitaya scope")
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
    
    def init_property_layout(self):
        self.property_watch_timer = QtCore.QTimer()
        self.property_watch_timer.setInterval(1000)
        self.property_watch_timer.start()
        
        self.property_layout = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.property_layout)
        self.properties = []
        for prop in self.property_names:
            if hasattr(self.rp.scope, prop + 's'):
                new_prop = ComboProperty(prop, self)
            elif isinstance(getattr(self.rp.scope, prop), bool):
                new_prop = BoolProperty(prop, self)
            else:
                new_prop = NumberProperty(prop, self)
            self.properties.append(new_prop)
                
    def update_properties(self):
        for prop in self.properties:
            prop.update_widget()
        

class RedPitayaGui(RedPitaya):
    def gui(self):
        self.gui_timer = QtCore.QTimer()
        self.scope_widget = ScopeWidget(parent=None, redpitaya=self)
        self.scope_widget.show()
        










