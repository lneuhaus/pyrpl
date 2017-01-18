import logging

logger = logging.getLogger(name=__name__)

from pyrpl import Pyrpl
from pyrpl.widgets.attribute_widgets import SelectAttributeWidget, BoolAttributeWidget, NumberAttributeWidget
from pyrpl.attributes import BoolAttribute, NumberAttribute, SelectAttribute
from pyrpl.redpitaya import RedPitaya
from PyQt4.QtTest import QTest
from PyQt4.QtCore import Qt
import os

class TestClass(object):
    @classmethod
    def setUpAll(self):
        ## these tests currently do not run on travis.
        ## our workaround is this: detect from environment variable
        ## if tests are executed on travis and refuse the gui tests
        try:
            skip = os.environ["REDPITAYA_SKIPGUITEST"]
        except KeyError:
            self.do_gui_tests = True
        else:
            self.do_gui_tests = False

        if self.do_gui_tests:
            filename = os.path.join(os.path.split(os.path.dirname(__file__))[0], 'config', 'tests_temp.yml')
            if os.path.exists(filename):
                os.remove(filename)
            self.pyrpl = Pyrpl(config="tests_temp", source="tests_source")
            self.r = self.pyrpl.rp
        else:
            self.pyrpl = None

    def test_scope_widget(self):
        if self.pyrpl is None:
            return
        widget = self.pyrpl.rp.scope.create_widget()
        for attr in widget.attribute_widgets:
            if isinstance(attr, SelectAttributeWidget):
                for option in attr.options:
                    to_set = attr.widget.findText(str(option)) # it would be a pain in the ** to
                                                               #  select an element with a QTest
                    attr.widget.setCurrentIndex(to_set)
                    assert (getattr(self.pyrpl.rp.scope, attr.name)==option)
            elif isinstance(attr, BoolAttributeWidget):
                for i in range(2):
                    QTest.mouseClick(attr.widget, Qt.LeftButton)
                    assert (getattr(self.pyrpl.rp.scope, attr.name)\
                            ==(attr.widget.checkState()==2))
            elif isinstance(attr, NumberAttributeWidget):
                for i in range(3):
                    attr.widget.stepUp()
                    assert(abs(getattr(self.pyrpl.rp.scope, attr.name) - \
                               attr.widget.value())<0.0001)

    def test_asg_gui(self):
        if self.pyrpl is None:
            return
        for asg in [mod for mod in self.pyrpl.asgs.all_modules]:
            self.try_gui_module(asg.create_widget())

    def try_gui_module(self, module_widget): # name should not start with test
        if not self.do_gui_tests:
            return
        module = module_widget.module
        for attr in module.gui_attributes:
            if isinstance(attr, SelectAttribute):
                for option in attr.options:
                    to_set = attr.widget.findText(str(option))
                    attr.widget.setCurrentIndex(to_set)
                    assert (getattr(module, attr.name) == option)
            elif isinstance(attr, BoolAttribute):
                for i in range(2):
                    QTest.mouseClick(attr.widget, Qt.LeftButton)
                    assert (getattr(module, attr.name) \
                            == (attr.widget.checkState() == 2))
            elif isinstance(attr, NumberAttribute):
                for i in range(3):
                    attr.widget.stepUp()
                    val = getattr(module, attr.name)
                    wid_val = attr.widget.value()
                    err = abs((val - wid_val)/max(val, 1.))
                    assert(err < 0.001)
