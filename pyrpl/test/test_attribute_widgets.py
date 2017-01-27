import logging
logger = logging.getLogger(name=__name__)
import numbers
from ..modules import SoftwareModule
from ..attributes import BoolProperty, FilterProperty, SelectProperty, \
    FloatProperty
from .test_base import TestPyrpl


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


class TestClass(TestPyrpl):
    source_config_file = "tests_source_dummy_module"

    def test_module_attributes(self):
        assert("DummyModule" in self.pyrpl.c.pyrpl.modules)
        return
        assert(isinstance(self.pyrpl.dummy_module.true_or_false, bool))
        assert(isinstance(self.pyrpl.dummy_module.some_number, float))
        assert(isinstance(self.pyrpl.dummy_module.some_filter, numbers.Number)) #should this be a list ?
        assert(isinstance(self.pyrpl.dummy_module.some_options, basestring))
