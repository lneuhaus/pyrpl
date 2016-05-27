from pyrpl import RedPitaya
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg

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

    def run_single(self):
        self.rp.scope.setup()
        self.plot_item.enableAutoRange('xy', True)
        self.curve.setData(self.rp.scope.curve())


    def do_run_continuous(self):
        if self.rp.scope.curve_ready():
            self.curve.setData(self.rp.scope.curve())
            if self.first_shot_of_continuous:
                self.first_shot_of_continuous = False
                self.plot_item.enableAutoRange('xy', False)
            self.rp.scope.setup()
        self.timer.start()

    

        
    def run_continuous(self):
        if str(self.rp.scope_widget.button_continuous.text())\
                   =="Run continuous":
            self.button_continuous.setText("Stop")
            self.rp.scope.setup()
            self.plot_item.enableAutoRange('xy', True)
            self.first_shot_of_continuous = True
            self.timer.start()
        else:
            self.button_continuous.setText("Run continuous")
            self.timer.stop()

    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Redpitaya scope")
        self.win = pg.GraphicsWindow(title="Scope")
        self.plot_item = self.win.addPlot(title="Scope")
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.curve = self.plot_item.plot(pen='y')
        self.main_layout.addWidget(self.win)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.main_layout.addLayout(self.button_layout)

class RedPitayaGui(RedPitaya):
    def gui(self):
        self.gui_timer = QtCore.QTimer()
        self.scope_widget = ScopeWidget(parent=None, redpitaya=self)
        self.scope_widget.show()
        










