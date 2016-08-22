from PyQt4 import QtCore, QtGui


class MyStateButton(QtGui.QPushButton):
    def __init__(self, name, color, parent):
        super(MyStateButton, self).__init__(name)
        self.setStyleSheet("""QPushButton {
                                    color:%s;
                                    }
                              QPushButton:checked{
                                    background-color: %s;
                                    color:#FFFFFF;
                                    border: none;
                                    }"""%(color, color))
                             # QPushButton:hover{
                             #       background-color: grey;
                             #       border-style: outset;
                             #       }  """%(color, color))
        self.name = name
        self.setCheckable(True)
        #self.setMinimumHeight(120)
        self.parent = parent
        self.toggled.connect(self.touched)
        self.setSizePolicy(QtGui.QSizePolicy.Expanding,
                           QtGui.QSizePolicy.Expanding)

    def touched(self):
        #if self.isChecked(): # could use a QButtonGroup instead, but I wan't
        #to be able to uncheck buttons to unlock
        self.parent.update_buttons(self.name)
        self.parent.pyrpl.lock(firststage=self.name, laststage=self.name)



class PyrplGui(QtGui.QWidget):
    def __init__(self, pyrpl, parent=None):
        super(PyrplGui, self).__init__(parent)

        self.pyrpl = pyrpl


        self.lay = QtGui.QHBoxLayout()
        self.setLayout(self.lay)
        self.layout_manage_lock = QtGui.QVBoxLayout()
        self.lay.addLayout(self.layout_manage_lock)

        self.button_unlock = QtGui.QPushButton("Unlock")
        self.button_unlock.clicked.connect(self.pyrpl.unlock)
        self.layout_manage_lock.addWidget(self.button_unlock)
        self.button_sweep = QtGui.QPushButton("Sweep")
        self.layout_manage_lock.addWidget(self.button_sweep)

        self.lock_layout = QtGui.QHBoxLayout()
        self.button_run_all = QtGui.QPushButton("Run all >>>")
        self.button_reload = QtGui.QPushButton("Reload")
        self.layout_manage_lock.addWidget(self.button_run_all)
        self.layout_manage_lock.addWidget(self.button_reload)
        self.button_reload.clicked.connect(self.display_lock)
        # self.button_run_all.setMinimumHeight(60)
        self.layout_manage_lock.addWidget(self.button_run_all)

        self.button_run_all.clicked.connect(self.pyrpl.model.lock)

        for button in self.button_sweep, self.button_unlock, \
                      self.button_reload,self.button_run_all:
            button.setSizePolicy(QtGui.QSizePolicy.Fixed,
                                 QtGui.QSizePolicy.Expanding)

        self.lay.setSpacing(0)
        self.lay.addLayout(self.layout_manage_lock)
        self.lay.addLayout(self.lock_layout)

        self.pyrpl.model.stage_changed_hook = self.update_buttons

        self.button_sweep.clicked.connect(self.pyrpl.sweep)

        self.stage_buttons = []
        self.display_lock()

        self.timer_stage = QtCore.QTimer()
        self.timer_stage.setInterval(200)
        self.timer_stage.timeout.connect(self.update_from_model)
        self.timer_stage.start()

    def display_lock(self):
        while self.stage_buttons:
            self.stage_buttons.pop().deleteLater()

        tot = len(self.pyrpl.model._config.lock.stages._keys())
        for index, stage in enumerate(self.pyrpl.model._config.lock.stages\
                ._keys()):
            button = MyStateButton(stage, "rgb(%i,%i,0)"%(255*(tot -
                                                               index)/tot,
                                                          255*index/tot),
                                   self)
            self.stage_buttons.append(button)
            self.lock_layout.addWidget(button)

    def update_buttons(self, new_stage):
        for button in self.stage_buttons:
            button.blockSignals(True)
            button.setChecked(button.name==new_stage)
            button.blockSignals(False)

    def update_from_model(self):
        self.update_buttons(self.pyrpl.model.current_stage)

    def next_stage(self):
        pass

