import logging
logger = logging.getLogger(name=__name__)
from pyrpl.attributes import *
from pyrpl.test.test_base import TestPyrpl
from pyrpl.software_modules import *
from pyrpl.software_modules.module_managers import *
from pyrpl.hardware_modules import *
from pyrpl.modules import *
from pyrpl import APP
from pyrpl.async_utils import sleep as async_sleep
from qtpy import QtCore


def scramble_values(mod,
                    str_val='foo',
                    num_val=12.0,
                    bool_val=True,
                    list_val=[1912],
                    option_index=0,
                    list_length=4):
    """
    This function tries to modify all _setup_attributes of the module :code:`mod`.

    The arguments specify the new values for each type of Attribute.

    Args:
        mod: Module whose values are to be scrambled.
        str_val: string value
        num_val: number value
        bool_val: etc...
        list_val:
        option_index:
        list_length:

    Returns:
        attr_names, attr_vals: lists of all modified attribute names and the set values.
    """
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
        elif isinstance(val, str):  # used to be basestring
            val = str_val
        if isinstance(val, bool):
            val = bool_val
        if isinstance(val, numbers.Number):
            val += num_val
        if isinstance(mod, list):
            val = list_val
        if attr == 'center':  # iq mode not supported yet for specan
            val = 0
        if attr=='baseband':  # iq mode not supported yet for specan
            val = True
        try:
            setattr(mod, attr, val)
        except ValueError as e:
            if not str(e)=="Nonzero center frequency not allowed in baseband mode.":
                raise
        val = getattr(mod, attr)
        attr_names.append(attr)
        attr_vals.append(val)
    return attr_names, attr_vals


class TestLoadSave(TestPyrpl):
    """
    iterates over all modules, prepares a certain state, saves this,
    messes up the current state, loads the saved state and checks whether
    attributes are the ones that were saved
    """

    def test_load_save(self):
        for mod in self.pyrpl.modules:
            #for exclude in [Lockbox, Scope]: # scope has an unknown bug
            # here (nosetests freezes at a  later time)
            for exclude in [Lockbox]:  # lockbox is tested elsewhere
                if isinstance(mod, exclude):
                    break
            else:
                yield self.assert_load_save_module, mod
                # make sure all modules are stopped at the end of this test
                try:
                    mod.stop()
                except:
                    pass

    def assert_load_save_module(self, mod):
        if not isinstance(mod, ModuleManager):
            mod._logger.info("Testing LoadSave of module %s", mod.name)
            if isinstance(mod, SpectrumAnalyzer):
                mod.setup(baseband=True) # iq mod not supported yet
            attr_names, attr_vals = scramble_values(
                                 mod, 'foo', 12.1, True, [1923], 0, 5)
            mod.save_state('test_save')
            scramble_values(mod, 'bar', 13.2, False,  [15], 1, 7)
            mod.load_state('test_save')
            for attr, attr_val in zip(mod._setup_attributes, attr_vals):
                if attr == 'default_sweep_output' or attr == 'baseband':
                    continue  # anyways, this will be redesigned soon with a proper link to the output...
                if attr == 'd':  # derivators are deactivated
                    pass
                elif attr == 'sequence':
                    assert len(getattr(mod, attr)) == len(attr_val), "sequence"
                else:
                    assert getattr(mod, attr)==attr_val, (mod, attr, attr_val, getattr(mod, attr))
                async_sleep(0.01)  # randomly inserted in fear of bugs
        async_sleep(0.1)  # randomly inserted in fear of bugs

