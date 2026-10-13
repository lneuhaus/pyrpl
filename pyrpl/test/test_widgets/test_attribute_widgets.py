import logging

import numpy as np
import pytest
from qtpy import QtCore, QtTest

from pyrpl import APP
from pyrpl.async_utils import sleep
from pyrpl.hardware_modules.iir import IIR
from pyrpl.hardware_modules.pid import Pid
from pyrpl.software_modules import NetworkAnalyzer
from pyrpl.test.test_base import TestPyrpl
from pyrpl.widgets.attribute_widgets import NumberAttributeWidget

# passes on the simulated (_FAKE_) Red Pitaya too
pytestmark = pytest.mark.simulation

logger = logging.getLogger(name=__name__)


class TestAttributeWidgets(TestPyrpl):
    # somehow the file seems to suffer from other nosetests, so pick an
    # individual name for this test:
    # tmp_config_file = "nosetests_config_scope.yml"

    def teardown_method(self):
        pass

    # def test_spin_box(self):
    #     for mod in self.pyrpl.modules:
    #         if not isinstance(mod, (IIR, NetworkAnalyzer)): # TODO:
    #             # understand what freezes with Na and IIR...
    #             widget = mod._create_widget()
    #             for name, aw in widget.attribute_widgets.items():
    #                 if isinstance(aw, NumberAttributeWidget):
    #                     yield self.assert_spin_box, mod, widget, name, aw

    def test_spin_box_pytest(self, subtests):
        for mod in self.pyrpl.modules:
            if not isinstance(mod, (IIR, NetworkAnalyzer)):  # TODO:
                # understand what freezes with Na and IIR...
                widget = mod._create_widget()
                for name, aw in widget.attribute_widgets.items():
                    if isinstance(aw, NumberAttributeWidget):
                        with subtests.test(mod=mod, name=name):
                            self.assert_spin_box(mod, widget, name, aw)

    _TEST_SPINBOX_BUTTON_DOWN_TIME = 0.05

    def assert_spin_box(self, mod, widget, name, aw):
        print(f"Testing spinbox widget for {mod.name}.{name}...")
        # make sure the module is not reserved by some other module
        # (as this would disable the key press response)
        mod.free()
        APP.processEvents()
        # save original value for later
        original_m_value = getattr(mod, name)
        original_i = mod.i if isinstance(mod, Pid) and name == "ival" else None
        if original_i is not None:
            # Releasing ownership does not stop a running PID. Freeze its
            # integrator so the hardware cannot modify ival between the model
            # assignment and the widget comparison.
            mod.i = 0

        try:
            # set attribute in the middle between minimum and maximum
            maximum = aw.widget.maximum if np.isfinite(aw.widget.maximum) else 10000000
            minimum = aw.widget.minimum if np.isfinite(aw.widget.minimum) else -10000000
            setattr(mod, name, (maximum + minimum) / 2)
            APP.processEvents()
            w_value = aw.widget_value
            m_value = getattr(mod, name)
            norm = 1 if (m_value == 0 or w_value == 0) else m_value
            assert abs(w_value - m_value) / norm < 0.001, (w_value, m_value, mod.name, name)

            # some widgets are disabled by default and must be skipped
            fullname = f"{mod.name}.{name}"
            exclude = ["spectrumanalyzer.center"]
            if fullname in exclude:
                print(f"Widget {mod.name}.{name} was not enabled and cannot be tested...")
                return

            # go up
            QtTest.QTest.keyPress(aw, QtCore.Qt.Key_Up)
            sleep(self._TEST_SPINBOX_BUTTON_DOWN_TIME)
            QtTest.QTest.keyRelease(aw, QtCore.Qt.Key_Up)
            sleep(self._TEST_SPINBOX_BUTTON_DOWN_TIME)
            new_val = getattr(mod, name)
            assert new_val > m_value, (new_val, m_value, mod.name, name)

            # go down
            QtTest.QTest.keyPress(aw, QtCore.Qt.Key_Down)
            sleep(self._TEST_SPINBOX_BUTTON_DOWN_TIME)
            QtTest.QTest.keyRelease(aw, QtCore.Qt.Key_Down)
            sleep(self._TEST_SPINBOX_BUTTON_DOWN_TIME)
            new_new_val = getattr(mod, name)
            assert new_new_val < new_val, (new_new_val, new_val, mod.name, name)
        finally:
            # Always restore hardware state, including when a subtest fails.
            setattr(mod, name, original_m_value)
            if original_i is not None:
                mod.i = original_i
