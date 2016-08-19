from PyQt4 import QtCore, QtGui


class CurrentStageWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        super(CurrentStageWidget, self).__init__(parent)
        self.lay = QtGui.QVBoxLayout()
        self.label = QtGui.QLabel("Current stage:")
        self.display = QtGui.QLabel('Unlocked')
        self.lay.addWidget(self.label)
        self.lay.addWidget(self.display)
        self.setLayout(self.lay)

class PyrplGui(QtGui.QWidget):
    def __init__(self, pyrpl, parent=None):
        super(PyrplGui, self).__init__(parent)

        self.pyrpl = pyrpl

        self.lay = QtGui.QVBoxLayout()
        self.setLayout(self.lay)
        self.button_sweep = QtGui.QPushButton("Sweep")
        self.lay.addWidget(self.button_sweep)

        self.current_stage_widget = CurrentStageWidget()
        self.lay.addWidget(self.current_stage_widget)

        self.lock_layout = QtGui.QHBoxLayout()
        self.lay.addLayout(self.lock_layout)
        self.button_unlock = QtGui.QPushButton("Unlock")
        self.lock_layout.addWidget(self.button_unlock)

        self.button_next = QtGui.QPushButton("Next stage")
        self.lock_layout.addWidget(self.button_next)
        self.button_full_sequence = QtGui.QPushButton("Full sequence")
        self.lock_layout.addWidget(self.button_full_sequence)

        self.button_sweep.clicked.connect(self.pyrpl.sweep)
        self.button_unlock.clicked.connect(self.pyrpl.unlock)
        self.button_next.clicked.connect(self.next_stage)

    def next_stage(self):
        pass

