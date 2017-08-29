import logging
logger = logging.getLogger(name=__name__)
from qtpy.QtTest import QTest
from qtpy.QtCore import Qt
import os
from ..widgets.attribute_widgets import SelectAttributeWidget, BoolAttributeWidget, NumberAttributeWidget
from ..attributes import BoolProperty, NumberProperty, SelectProperty
from .test_base import TestPyrpl


class TestModuleWidgets(TestPyrpl):
    @classmethod
    def setup(self):
        ## these tests currently do not run on travis.
        ## our workaround is this: detect from environment variable
        ## if tests are executed on travis and refuse the gui tests
        try:
            skip = os.environ["REDPITAYA_SKIPGUITEST"]
        except KeyError:
            self.do_gui_tests = True
        else:
            self.do_gui_tests = False

        if not self.do_gui_tests:
            self.pyrpl = None

    def test_scope_widget(self):
        if self.pyrpl is None:
            return
        widget = self.pyrpl.rp.scope._create_widget()
        for attr in widget.attribute_widgets:
            if isinstance(attr, SelectAttributeWidget):
                for option in attr.options:
                    to_set = attr.widget.findText(str(option))
                    # it would be a pain to select an element with a QTest
                    attr.widget.setCurrentIndex(to_set)
                    assert (getattr(self.pyrpl.rp.scope, attr.attribute_name) == option)
            elif isinstance(attr, BoolAttributeWidget):
                for i in range(2):
                    QTest.mouseClick(attr.widget, Qt.LeftButton)
                    assert (getattr(self.pyrpl.rp.scope, attr.attribute_name) ==
                        (attr.widget.checkState() == 2))
            elif isinstance(attr, NumberAttributeWidget):
                for i in range(3):
                    attr.widget.stepUp()
                    assert(abs(getattr(self.pyrpl.rp.scope, attr.attribute_name) -
                               attr.widget.value()) < 0.0001)

    def test_asg_gui(self):
        if self.pyrpl is None:
            return
        for asg in [mod for mod in self.pyrpl.asgs.all_modules]:
            self.try_gui_module(asg._create_widget())

    def try_gui_module(self, module_widget): # name should not start with test
        if not self.do_gui_tests:
            return
        module = module_widget.module
        for attr in module._gui_attributes:
            if isinstance(attr, SelectProperty):
                for option in attr.options(module):
                    to_set = attr.widget.findText(str(option))
                    attr.widget.setCurrentIndex(to_set)
                    assert (getattr(module, attr.name) == option)
            elif isinstance(attr, BoolProperty):
                for i in range(2):
                    QTest.mouseClick(attr.widget, Qt.LeftButton)
                    assert (getattr(module, attr.name)
                            == (attr.widget.checkState() == 2))
            elif isinstance(attr, NumberProperty):
                for i in range(3):
                    attr.widget.stepUp()
                    val = getattr(module, attr.name)
                    wid_val = attr.widget.value()
                    err = abs((val - wid_val)/max(val, 1.))
                    assert(err < 0.001)
