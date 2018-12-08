import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from qtpy import QtCore, QtWidgets
from pyrpl.test.test_base import TestPyrpl
from pyrpl import APP
from pyrpl.curvedb import CurveDB
from pyrpl.widgets.startup_widget import HostnameSelectorWidget
from pyrpl.async_utils import sleep_async
from pyrpl.widgets.yml_editor import YmlEditor
from pyrpl.software_modules.module_managers import ModuleManager

class TestYmlEditor(TestPyrpl):
    # somehow the file seems to suffer from other nosetests, so pick an
    # individual name for this test:
    # tmp_config_file = "nosetests_config_scope.yml"

    def teardown(self):
        pass

    def test_yml_editor(self):
        for mod in self.pyrpl.modules:
            if not isinstance(mod, ModuleManager):
                widg = YmlEditor(mod, None) # Edit current state
                widg.show()
                widg.load_all()
                widg.save()
                widg.cancel()
