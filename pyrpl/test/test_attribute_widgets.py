from pyrpl.modules import SoftwareModule
from pyrpl.attributes import BoolProperty
from pyrpl import Pyrpl

import os
import logging
logger = logging.getLogger(name=__name__)

class TestClass(object):
    @classmethod
    def setUpAll(self):
        filename = os.path.join(os.path.split(os.path.dirname(__file__))[0], 'config', 'tests_temp.yml')
        if os.path.exists(filename):
            os.remove(filename)
        self.pyrpl = Pyrpl(config="tests_temp", source="tests_source")
        self.r = self.pyrpl.rp
"""
    def test_module_attributes(self):
        class DummyModule(SoftwareModule):
            section_name = "dummy_module"
            gui_attributes = ['true_or_false']
            true_or_false = BoolProperty()

        d = DummyModule(self.pyrpl)
        assert(isinstance(d.true_or_false, bool))

    def test_software_module_widget(self):
        class DummyModule(SoftwareModule):
            gui_attributes = ['true_or_false']
            true_or_false = BoolProperty()

        d = DummyModule(self.pyrpl)
        d.create_widget()
"""