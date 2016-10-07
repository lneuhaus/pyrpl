#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
ZetCode PyQt4 tutorial

This program shows a confirmation
message box when we click on the close
button of the application window.

author: Jan Bodnar
website: zetcode.com
last edited: October 2011
"""

import sys
import pyrpl
from PyQt4 import QtGui, QtCore


class Example(QtGui.QMainWindow):
    def __init__(self):
        super(Example, self).__init__()
        self.SHGLock = pyrpl.SL()
        #self.initUI()

    def initUI(self):

        # buttons
        qbtn = QtGui.QPushButton('Quit', self)
        qbtn.clicked.connect(QtCore.QCoreApplication.instance().quit)
        run_catlab_rp2 = QtGui.QPushButton("catlab2")
        run_catlab_rp3 = QtGui.QPushButton("catlab3_SHGLock")
        # buttons layout
        Buttons_layout_V = QtGui.QVBoxLayout()
        Buttons_layout_V.addWidget(run_catlab_rp2)
        Buttons_layout_V.addWidget(run_catlab_rp3)
        Buttons_layout_V.addWidget(qbtn)
        #
        Buttons_layout_H = QtGui.QHBoxLayout()
        Buttons_layout_H.addStretch(1)
        Buttons_layout_H.addLayout(Buttons_layout_V)
        Buttons_layout_H.addStretch(1)
        #
        Buttons_Widget = QtGui.QWidget()
        Buttons_Widget.setLayout(Buttons_layout_H)
        #
        self.setCentralWidget(Buttons_Widget)

        # add this and that
        #self.hehe()

        # center windows and message bar
        self.setGeometry(300, 300, 320, 240)
        self.setWindowTitle('Catlab RedPitaya manager')
        self.center()
        self.show()


    def hehe(self):

        #quit abstract action and shortcut
        exitAction = QtGui.QAction(QtGui.QIcon('exit.png'), '&Exit', self)
        exitAction.setShortcut('Ctrl+Q')
        exitAction.setStatusTip('Exit application')
        exitAction.triggered.connect(QtGui.qApp.quit)

        # quit menubar
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')
        fileMenu.addAction(exitAction)

        # set status bar
        self.statusBar().showMessage('Ready')



    def closeEvent(self, event):

        reply = QtGui.QMessageBox.question(self, 'Message',
                                           "Are you sure to quit?", QtGui.QMessageBox.Yes |
                                           QtGui.QMessageBox.No, QtGui.QMessageBox.No)

        if reply == QtGui.QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def center(self):

        qr = self.frameGeometry()
        cp = QtGui.QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())


def main():
    app = QtGui.QApplication(sys.argv)
    ex = Example()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()