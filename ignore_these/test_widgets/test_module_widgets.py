import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from pyrpl.async_utils import sleep as async_sleep
from qtpy import QtCore, QtWidgets
from pyrpl.test.test_base import TestPyrpl
from pyrpl import APP
from pyrpl.curvedb import CurveDB

class TestModuleWidgets(TestPyrpl):
    OPEN_ALL_DOCKWIDGETS = True  # forces all DockWidgets to become visible
