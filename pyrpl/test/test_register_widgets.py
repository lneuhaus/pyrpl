import logging
logger = logging.getLogger(name=__name__)

from pyrpl.hardware_modules.redpitaya_registers import *


class TestClass(object):
    @classmethod
    def setUpAll(self):
        pass


    def test_module_attributes(self):
        class DummyModule(SoftwareModule):
            gui_attributes = ['true_or_false']
            true_or_false = BoolProperty()

        d = DummyModule()
        assert(isinstance(d.true_or_false, bool))


    def test_software_module_widget(self):
        #if self.r is None:
        #    return

        class DummyModule(SoftwareModule):
            gui_attributes = ['true_or_false']
            true_or_false = BoolProperty()

        d = DummyModule()
        d.create_widget()