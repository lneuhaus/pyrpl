import logging
logger = logging.getLogger(name=__name__)
import numbers
from ..modules import Module
from ..attributes import BoolProperty, FilterProperty, SelectProperty, \
    FloatProperty
from .test_base import TestPyrpl

# This file was deteted. Is this supposed to be so?


class MyFilterProperty(FilterProperty):
    def valid_frequencies(self, module):
        return [2**n for n in range(14)]


class DummyModule(Module):
    _gui_attributes = ['true_or_false']
    true_or_false = BoolProperty()
    some_number = FloatProperty(min=-10, max=10, default=1.414)
    some_filter = MyFilterProperty()
    some_options = SelectProperty(options=["foo", "bar"])


class TestAttributeWidgets(TestPyrpl):
    source_config_file = "nosetests_source_dummy_module"

    def test_config_file(self):
        assert("DummyModule" in self.pyrpl.c.pyrpl.modules)

    def test_dummy_module(self):
        self.pyrpl.dummymodule._load_setup_attributes()
        assert(isinstance(self.pyrpl.dummymodule.true_or_false, bool))
        assert(isinstance(self.pyrpl.dummymodule.some_number, float))
        assert(isinstance(self.pyrpl.dummymodule.some_filter, numbers.Number)) #should this be a list ?
        assert(isinstance(self.pyrpl.dummymodule.some_options, str))  # used to be basestring
        # tried to add this, but the second assertion just doesnt seem to work
        assert (self.pyrpl.c.dummymodule.some_number == 3.123), \
                       self.pyrpl.c.dummymodule.some_number
        #assert (self.pyrpl.dummymodule.some_number == 3.123), \
        #                self.pyrpl.dummymodule.some_number