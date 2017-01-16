"""
Script to launch pyrpl from the command line.
Type python run_pyrpl [config_file_name]
To create a Pyrpl instance with the config file "config_file_name"
"""

from PyQt4 import QtCore, QtGui
from pyrpl import Pyrpl

import sys

if __name__=='__main__':
    if len(sys.argv) > 2:
        print("usage: python run_pyrpl.py [config_file_name]")
    if len(sys.argv) == 1:
        arg = None
    else:
        arg = sys.argv[1]
    print("Creating Pyrpl instance with the config file" + str(arg))
    PYRPL = Pyrpl(arg)
    APP = QtGui.QApplication.instance()
    APP.exec_()