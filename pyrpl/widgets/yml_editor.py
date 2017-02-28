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
        self.button_refresh = QtGui.QPushButton("Refresh")
        if self.state is None:
            save_txt = "Save + set!!!"
        else:
            save_txt = "Save"
        self.button_save = QtGui.QPushButton(save_txt)

        self.button_refresh.clicked.connect(self.refresh)
        self.button_save.clicked.connect(self.save)

        self.lay = QtGui.QVBoxLayout()
        self.setLayout(self.lay)
        self.lay.addWidget(self.editor)

        self.lay_h = QtGui.QHBoxLayout()
        self.lay.addLayout(self.lay_h)
        self.lay_h.addWidget(self.button_refresh)
        self.lay_h.addWidget(self.button_save)

        self.refresh()

    def sizeHint(self):
        return QtCore.QSize(500,500)

    def refresh(self):
        self.editor.setText(self.module.get_yml(self.state))

    def save(self):
        self.module.set_yml(str(self.editor.toPlainText()), state=self.state)