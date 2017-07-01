""" script to test the software, e.g. in PyCharm debugger, without actually having a redpitaya """

from pyrpl import Pyrpl
from qtpy import QtWidgets, QtCore

APP = QtWidgets.QApplication.instance()


p = Pyrpl(config="localtest", hostname="_FAKE_REDPITAYA_")

while True:
    APP.processEvents()

