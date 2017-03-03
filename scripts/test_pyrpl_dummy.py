from pyrpl import Pyrpl
from PyQt4 import QtGui, QtCore

APP = QtGui.QApplication.instance()
#p = Pyrpl(hostname="_DUMMY_")
p = Pyrpl(config="leotests_source", hostname="_DUMMY_")

while True:
    APP.processEvents()

