import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from ...async_utils import sleep as async_sleep
from qtpy import QtCore, QtWidgets
from ..test_base import TestPyrpl
from ... import APP
from ...curvedb import CurveDB

class TestModuleWidgets(TestPyrpl):
    """
    Be carreful to stop the scope at the end of each test!!!
    """
    # somehow the file seems to suffer from other nosetests, so pick an
    # individual name for this test:
    # tmp_config_file = "nosetests_config_scope.yml"

    def teardown(self):
        pass


    def test_create_widget(self):
        for mod in self.pyrpl.modules:
            widget = mod._create_widget()