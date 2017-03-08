from pyrpl import Pyrpl
from PyQt4 import QtGui, QtCore

APP = QtGui.QApplication.instance()

#p = Pyrpl(hostname="_FAKE_REDPITAYA_")
p = Pyrpl(config="leotests_source", hostname="_FAKE_REDPITAYA_")

while True:
    APP.processEvents()

