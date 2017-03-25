"""
Script to launch pyrpl from the command line.
Type python run_pyrpl [config_file_name]
To create a Pyrpl instance with the config file "config_file_name"
"""

from PyQt4 import QtCore, QtGui
from pyrpl import Pyrpl

import sys

if __name__ == '__main__':
    if len(sys.argv) > 3:
        print("usage: python run_pyrpl.py [[config]=config_file_name] "
              "[source=config_file_template] [hostname=hostname/ip]")
    kwargs = dict()
    for i, arg in enumerate(sys.argv):
        print (i, arg)
        if i == 0: # run_pyrpl.py
            continue
        k, v = arg.split('=', 1)
        if v == "":
            if i == 1:
                kwargs["config"]= k
        else:
            kwargs[k] = v
    print("Calling Pyrpl(**%s)"%str(kwargs))
    PYRPL = Pyrpl(**kwargs)
    APP = QtGui.QApplication.instance()
    APP.exec_()
