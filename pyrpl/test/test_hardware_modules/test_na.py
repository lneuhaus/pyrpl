import logging
import os

logger = logging.getLogger(name=__name__)

from pyrpl import RedPitaya, Pyrpl
from pyrpl.attributes import *

import time
from PyQt4 import QtCore, QtGui

APP = QtGui.QApplication.instance()


