import time


QT_EXIST = True
try:
    from PyQt4 import QtCore, QtGui
except ImportError:
    QT_EXIST = False

if QT_EXIST:
    APP = QtGui.QApplication.instance()

def sleep(time_s):
    """
    If PyQt4 is installed on the machine,
    calls processEvents regularly to make sure
     the GUI doesn't freeze.

     This function should be used everywhere in the
     project in place of "time.sleep"
    """

    if QT_EXIST:
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.setInterval(1000*time_s)
        timer.start()
        while(timer.isActive()):
            APP.processEvents()
    else:
        time.sleep(time_s)

class MyDoubleSpinBox(QtGui.QWidget):
    value_changed = QtCore.pyqtSignal()

    def __init__(self, label, min=-1, max=1, step=2.**(-13), parent=None):
        super(MyDoubleSpinBox, self).__init__(parent)

        self.min = min
        self.max = max

        self.lay = QtGui.QHBoxLayout()
        self.lay.setContentsMargins(0,0,0,0)
        self.lay.setSpacing(0)
        self.setLayout(self.lay)

        if label is not None:
            self.label = QtGui.QLabel(label)
            self.lay.addWidget(self.label)
        self.step = step
        self.decimals = 4

        self.down = QtGui.QPushButton('<')
        self.lay.addWidget(self.down)

        self.line = QtGui.QLineEdit()
        self.lay.addWidget(self.line)

        self.up = QtGui.QPushButton('>')
        self.lay.addWidget(self.up)
        self.timer_arrow = QtCore.QTimer()
        self.timer_arrow.setInterval(5)
        self.timer_arrow.timeout.connect(self.make_step)

        self.up.pressed.connect(self.timer_arrow.start)
        self.down.pressed.connect(self.timer_arrow.start)

        self.up.setMaximumWidth(15)
        self.down.setMaximumWidth(15)

        self.up.released.connect(self.timer_arrow.stop)
        self.down.released.connect(self.timer_arrow.stop)

        self.line.editingFinished.connect(self.validate)
        self.val = 0

        self.setMaximumWidth(200)
        self.setMaximumHeight(20)

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

    @property
    def val(self):
        return float(self.line.text())

    @val.setter
    def val(self, new_val):
        self.line.setText(("%."+str(self.decimals) + "f")%new_val)
        return new_val

    def make_step(self):
        if self.up.isDown():
            self.val+=self.step
        if self.down.isDown():
            self.val-=self.step
        self.validate()

    def validate(self):
        if self.val>self.max:
            self.val = self.max
        if self.val<self.min:
            self.val = self.min
        self.value_changed.emit()






