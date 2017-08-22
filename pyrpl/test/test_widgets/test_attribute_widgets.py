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
from ...widgets.spinbox import NumberSpinBox
from ...widgets.attribute_widgets import NumberAttributeWidget
from ...hardware_modules.iir import IIR
from ...software_modules import NetworkAnalyzer

from qtpy import QtTest, QtCore

class TestAttributeWidgets(TestPyrpl):
    # somehow the file seems to suffer from other nosetests, so pick an
    # individual name for this test:
    # tmp_config_file = "nosetests_config_scope.yml"

    def teardown(self):
        pass

    def test_spin_box(self):
        for mod in self.pyrpl.modules:
            if not isinstance(mod, (IIR, NetworkAnalyzer)): # TODO:
                # understand what freezes with Na and IIR...
                widget = mod._create_widget()
                for name, aw in widget.attribute_widgets.items():
                    if isinstance(aw, NumberAttributeWidget):
                        yield self.assert_spin_box, mod, widget, name, aw

    _TEST_SPINBOX_BUTTON_DOWN_TIME = 0.05

    def assert_spin_box(self, mod, widget, name, aw):
        print("Testing widget for %s.%s..." %(mod.name, name))
        # make sure the module is not reserved by some other module
        # (as this would disable the key press response)
        mod.free()

        # set attribute in the middle between minimum and maximum
        maximum = aw.widget.maximum if np.isfinite(
                                aw.widget.maximum) else 10000000
        minimum = aw.widget.minimum if np.isfinite(
            aw.widget.minimum) else -10000000
        setattr(mod, name, (maximum + minimum)/2)
        w_value = aw.widget_value
        m_value = getattr(mod, name)
        norm = 1 if m_value==0 else m_value
        assert abs(w_value - m_value)/norm < 0.001, \
            (w_value, m_value, mod.name, name)

        # some widgets are disabled by default and must be skipped
        fullname = "%s.%s" % (mod.name, name)
        exclude = ['spectrumanalyzer.center']
        if fullname in exclude:
            # skip test for those
            print("Widget %s.%s was not enabled and cannot be tested..."
                  % (mod.name, name))
            return

        # go up
        QtTest.QTest.keyPress(aw, QtCore.Qt.Key_Up)
        sleep(self._TEST_SPINBOX_BUTTON_DOWN_TIME)
        QtTest.QTest.keyRelease(aw, QtCore.Qt.Key_Up)
        new_val = getattr(mod, name)
        assert(new_val > m_value), (new_val, m_value, mod.name, name)

        # go down
        QtTest.QTest.keyPress(aw, QtCore.Qt.Key_Down)
        sleep(self._TEST_SPINBOX_BUTTON_DOWN_TIME)
        QtTest.QTest.keyRelease(aw, QtCore.Qt.Key_Down)
        new_new_val = getattr(mod, name)
        assert (new_new_val < new_val), (new_new_val, new_val, mod.name, name)