import logging
import os

logger = logging.getLogger(name=__name__)

from pyrpl import RedPitaya, Pyrpl
from pyrpl.attributes import *
from pyrpl.bijection import Bijection
from pyrpl.software_modules.module_managers import ModuleManager

import time

from pyrpl import CurveDB

class TestClass(object):
    @classmethod
    def setUpAll(self):
        self.pyrpl = Pyrpl(config="tests_temp", source="tests_source")
        self.r = self.pyrpl.rp

    def scramble_values(self, mod, str_val='foo', num_val=12, bool_val=True, list_val=[19], option_index=0):
        attr_names =[]
        attr_vals = []
        for attr in mod.setup_attributes:
            val = getattr(mod, attr)
            if isinstance(val, basestring):
                desc = getattr(mod.__class__, attr)
                if hasattr(desc, 'options'):
                    val = desc.options[option_index]
                else:
                    val = str_val
            if isinstance(val, numbers.Number):
                val += num_val
            if isinstance(val, bool):
                val = bool_val
            if isinstance(mod, list):
                val = list_val
            try:
                setattr(mod, attr, val)
            except ValueError as e:
                if not str(e)=="Nonzero center frequency not allowed in baseband mode.":
                    raise

            val = getattr(mod, attr)
            attr_names.append(attr)
            attr_vals.append(val)
        return attr_names, attr_vals

    def assert_load_save_module(self, mod):
        if not isinstance(mod, ModuleManager):
            attr_names, attr_vals = self.scramble_values(mod)
            mod.save_state('test_save')
            self.scramble_values(mod, 'bar', 13, False, [15], 1)
            mod.load_state('test_save')
            for attr, attr_val in zip(mod.setup_attributes, attr_vals):
                if attr!='d': # derivators are deactivated
                    assert getattr(mod, attr)==attr_val, (mod, attr, attr_val)

    def test_load_save(self):
        for mod in self.pyrpl.modules:
            yield self.assert_load_save_module, mod

    def test_raise_error(self):
        pass