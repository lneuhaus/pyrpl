import logging
logger = logging.getLogger(name=__name__)
import numbers
from ..modules import SoftwareModule
from ..attributes import BoolProperty, FilterProperty, SelectProperty, \
    FloatProperty, ModuleProperty
from .test_base import TestPyrpl


class MyFilterProperty(FilterProperty):
    def valid_frequencies(self, module):
        return [2**n for n in range(14)]


class FirstSubModule(SoftwareModule):
    _section_name = None
    _setup_attributes = ['b1', 'b2']
    b1 = BoolProperty()
    b2 = BoolProperty()


class SecondSubModule(SoftwareModule):
    _section_name = 'sub2'
    _setup_attributes = ['b1', 'b2']
    b1 = BoolProperty()
    b2 = BoolProperty()


class DummyModule(SoftwareModule):
    _section_name = "dummy_module"
    _gui_attributes = ['true_or_false']
    _setup_attributes = ['sub1', 'sub2']
    true_or_false = BoolProperty()
    some_number = FloatProperty(min=-10, max=10)
    some_filter = MyFilterProperty()
    some_options = SelectProperty(options=["foo", "bar"])
    sub1 = ModuleProperty(FirstSubModule)
    sub2 = ModuleProperty(SecondSubModule)


class TestClass(TestPyrpl):
    source_config_file = "tests_source_dummy_module"

    def setup(self):
        self.sub1 = self.pyrpl.dummy_module.sub1
        self.sub2 = self.pyrpl.dummy_module.sub2

    def test_config_file(self):
        assert("DummyModule" in self.pyrpl.c.pyrpl.modules)

    def test_dummy_module(self):
        assert(isinstance(self.pyrpl.dummy_module.true_or_false, bool))
        assert(isinstance(self.pyrpl.dummy_module.some_number, float))
        assert(isinstance(self.pyrpl.dummy_module.some_filter, numbers.Number)) #should this be a list ?
        assert(isinstance(self.pyrpl.dummy_module.some_options, basestring))

    def test_submodule(self):
        assert(self.sub1.b1==True) # values defined in config file
        assert(self.sub1.b2==False)

        self.sub2.b1 = True
        self.sub2.b2 = False
        assert(self.sub2.b1==True)
        assert(self.sub2.b2==False)

        self.pyrpl.dummy_module.save_state("true_false_true_false")

        self.sub1.b1 = False
        self.sub1.b2 = True
        assert(self.sub1.b1==False)
        assert(self.sub1.b2==True)

        self.sub2.b1 = False
        self.sub2.b2 = True
        assert(self.sub2.b1==False)
        assert(self.sub2.b2==True)

        self.pyrpl.dummy_module.load_state("true_false_true_false")
        assert(self.sub1.b1==True)
        assert(self.sub1.b2==False)
        assert(self.sub2.b1==True)
        assert(self.sub2.b2==False)

