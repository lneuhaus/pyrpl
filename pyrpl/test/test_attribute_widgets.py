from pyrpl.modules import SoftwareModule
from pyrpl.attributes import BoolProperty, FilterProperty, SelectProperty, FloatProperty
from pyrpl import Pyrpl

import os
import logging
import numbers
logger = logging.getLogger(name=__name__)


class MyFilterProperty(FilterProperty):
    def valid_frequencies(self, module):
        return [2**n for n in range(14)]

class DummyModule(SoftwareModule):
    section_name = "dummy_module"
    gui_attributes = ['true_or_false']
    true_or_false = BoolProperty()
    some_number = FloatProperty(min=-10, max=10)
    some_filter = MyFilterProperty()
    some_options = SelectProperty(options=["foo", "bar"])


class TestClass(object):
    @classmethod
    def setUpAll(self):
        filename = os.path.join(os.path.split(os.path.dirname(__file__))[0], 'config', 'user_config', 'tests_temp.yml')
        if os.path.exists(filename):
            os.remove(filename)
        self.pyrpl = Pyrpl(config="tests_temp_dummy_module", source="tests_source_dummy_module")
        # This config file contains - DummyModule in the section "software_modules"
        self.r = self.pyrpl.rp

    def test_module_attributes(self):
        assert(isinstance(self.pyrpl.dummy_module.true_or_false, bool))
        assert(isinstance(self.pyrpl.dummy_module.some_number, float))
        assert(isinstance(self.pyrpl.dummy_module.some_filter, numbers.Number)) #should this be a list ?
        assert(isinstance(self.pyrpl.dummy_module.some_options, basestring))