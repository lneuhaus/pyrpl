""" script to test the software, e.g. in PyCharm debugger, without actually having a redpitaya """

from pyrpl import Pyrpl
from PyQt4 import QtGui, QtCore

APP = QtGui.QApplication.instance()


p = Pyrpl(config="localtest", hostname="_FAKE_REDPITAYA_")

while True:
    APP.processEvents()

