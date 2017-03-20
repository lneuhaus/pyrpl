import os
from PyQt4 import QtGui
from pyrpl import Pyrpl, default_config_dir, user_config_dir

APP = QtGui.QApplication.instance()

from pyrpl import user_dir
print user_dir

print os.environ["PYRPL_USER_DIR"]
print default_config_dir
print user_config_dir

p = Pyrpl('fpf')
#p = Pyrpl(hostname="_FAKE_REDPITAYA_")
print p.c._filename

while True:
    APP.processEvents()
