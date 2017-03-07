from PyQt4 import QtCore, QtGui

class YmlEditor(QtGui.QWidget):
    def __init__(self, module, state):
        self.module = module
        self.state = state

        super(YmlEditor, self).__init__()
        if state is None:
            state = "current"
        self.setWindowTitle(".:Yml editor:. " + "Module: '" + \
                    str(self.module.name) +  "' State: '" + str(state) + "'")

        self.editor = QtGui.QTextEdit()
        self.button_cancel = QtGui.QPushButton("Cancel without saving")
        self.button_cancel.clicked.connect(self.cancel)
        self.button_refresh = QtGui.QPushButton("Load from file (refresh)")
        self.button_refresh.clicked.connect(self.refresh)
        self.button_load_all = QtGui.QPushButton("Load all current attributes from memory")
        self.button_load_all.clicked.connect(self.load_all)
        self.button_save = QtGui.QPushButton("Save to file + set to memory" if self.state is None else "Save to file")
        self.button_save.clicked.connect(self.save)

        self.lay = QtGui.QVBoxLayout()
        self.setLayout(self.lay)
        self.lay.addWidget(self.editor)

        self.lay_h = QtGui.QHBoxLayout()
        self.lay.addLayout(self.lay_h)
        self.lay_h.addWidget(self.button_cancel)
        self.lay_h.addWidget(self.button_refresh)
        self.lay_h.addWidget(self.button_load_all)
        self.lay_h.addWidget(self.button_save)

        self.refresh()

    def sizeHint(self):
        return QtCore.QSize(500,500)

    def cancel(self):
        self.close()

    def refresh(self):
        self.editor.setText(self.module.get_yml(self.state))

    def load_all(self):
        self.editor.setText(self.module.c._get_yml(data=self.module.setup_attributes))

    def save(self):
        self.module.set_yml(str(self.editor.toPlainText()), state=self.state)

