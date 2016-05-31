from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import NotReadyError
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import numpy as np

class ScopeWidget(QtGui.QWidget):
    def __init__(self, parent=None, redpitaya=None):
        super(ScopeWidget, self).__init__(parent)
        self.rp = redpitaya
        self.init_gui()
        self.button_single.clicked.connect(self.run_single)
        self.button_continuous.clicked.connect(self.run_continuous)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(10)
        self.timer.setSingleShot(True)
        
        self.timer.timeout.connect(self.do_run_continuous)

        for cb in self.cb_ch:
            cb.setCheckState(2)

        for cb in self.cb_ch:
            cb.stateChanged.connect(self.display_curves)

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
                self.curves[i-1].setVisible(True)
            else:
                self.curves[i-1].setVisible(False)

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
            self.button_single.setVisible(False)
            self.rp.scope.setup()
            self.plot_item.enableAutoRange('xy', True)
            self.first_shot_of_continuous = True
            self.timer.start()
        else:
            self.button_continuous.setText("Run continuous")
            self.timer.stop()
            self.button_single.setVisible(True)

    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Redpitaya scope")
        self.win = pg.GraphicsWindow(title="Scope")
        self.plot_item = self.win.addPlot(title="Scope")
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.curves = [self.plot_item.plot(pen=color) for color in ('r', 'b')]
        self.main_layout.addWidget(self.win)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.main_layout.addLayout(self.button_layout)
        self.cb_ch = []
        for i in (1,2):
            self.cb_ch.append(QtGui.QCheckBox("Channel "+str(i)))
            self.button_layout.addWidget(self.cb_ch[-1])
        

class RedPitayaGui(RedPitaya):
    def gui(self):
        self.gui_timer = QtCore.QTimer()
        self.scope_widget = ScopeWidget(parent=None, redpitaya=self)
        self.scope_widget.show()
        










