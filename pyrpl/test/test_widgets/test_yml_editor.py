import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from ...async_utils import sleep as async_sleep
from qtpy import QtCore, QtWidgets
from ..test_base import TestPyrpl
from ... import APP
from ...curvedb import CurveDB
from ...widgets.startup_widget import HostnameSelectorWidget
from ...async_utils import sleep
from ...widgets.yml_editor import YmlEditor
from ...software_modules.module_managers import ModuleManager

class TestYmlEditor(TestPyrpl):
    # somehow the file seems to suffer from other nosetests, so pick an
    # individual name for this test:
    # tmp_config_file = "nosetests_config_scope.yml"

    def teardown(self):
        pass


    def test_yml_editor(self):
        for mod in self.pyrpl.modules:
            if not isinstance(mod, ModuleManager):
                widg =  YmlEditor(mod, None) # Edit current state
                widg.show()
                widg.load_all()
                widg.save()
                widg.cancel()

