import logging
logger = logging.getLogger(name=__name__)
from ..attributes import *
from ..software_modules.module_managers import ModuleManager
from .test_base import TestPyrpl
from ..software_modules.lockbox.lockbox import Lockbox


class TestLoadSave(TestPyrpl):
    """ iterates over all modules, prepares a certain state, saves this,
    messes up the current state, loads the saved state and checks whether
    attributes are the ones that were saved"""
    def test_load_save(self):
        for mod in self.pyrpl.modules:
            if not isinstance(mod, Lockbox):  # exclude lockbox here since
                # it has too many special cases. it is teste in lockbox...
                yield self.assert_load_save_module, mod

    def test_raise_error(self):
        pass

    def scramble_values(self,
                        mod,
                        str_val='foo',
                        num_val=12,
                        bool_val=True,
                        list_val=[1912],
                        option_index=0,
                        list_length=4):
        attr_names =[]
        attr_vals = []
        for attr in mod._setup_attributes:
            if attr=='default_sweep_output':
                val = None# anyways, this will be redesigned soon with a proper link to the output...
            elif attr=='sequence':
                val = [{}] * list_length
            else:
                val = getattr(mod, attr)
            desc = getattr(mod.__class__, attr)
            if isinstance(desc, SelectProperty):
                val = list(desc.options(mod).keys())[option_index % len(desc.options(mod))]
            elif isinstance(val, basestring):
                val = str_val
            if isinstance(val, bool):
                val = bool_val
            if isinstance(val, numbers.Number):
                val += num_val
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
            attr_names, attr_vals = self.scramble_values(
                                 mod, 'foo', 12, True, [1923], 0, 5)
            mod.save_state('test_save')
            self.scramble_values(mod, 'bar', 13, False,  [15], 1, 7)
            mod.load_state('test_save')
            for attr, attr_val in zip(mod._setup_attributes, attr_vals):
                if attr == 'default_sweep_output' or attr == 'baseband':
                    continue  # anyways, this will be redesigned soon with a proper link to the output...
                if attr == 'd':  # derivators are deactivated
                    pass
                elif attr == 'sequence':
                    assert len(getattr(mod, attr)) == len(attr_val), "sequence"
                else:
                    assert getattr(mod, attr)==attr_val, (mod, attr, attr_val)
