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


class TestValidateAndNormalize(TestPyrpl):
    """
    ensures that the result of validate_and_normalize corresponds
    to the value the register actually contains for a number of random
    changes to all registers
    """

    def test_validate_and_normalize(self):
        for mod in self.pyrpl.modules:
            for exclude in [Lockbox]:  # lockbox is too complicated here
                if isinstance(mod, exclude):
                    break
            else:
                yield self.assert_validate_and_normalize, mod
                # make sure all modules are stopped at the end of this test
                try:
                    mod.stop()
                except:
                    pass

    def assert_validate_and_normalize(self, mod):
        self.results = []

        def check_fpga_value_equals_signal_value(attr_name, list_value):
            print("check_fpga_value_equals_signal_value(%s.%s, %s) was called!"
                  % (mod.name, attr_name, list_value))
            # add an entry to results
            self.results.append(("%s.%s" % (mod.name, attr_name), list_value[0], getattr(mod, attr_name)))

        mod._signal_launcher.update_attribute_by_name.connect(check_fpga_value_equals_signal_value)
        attr_names, attr_vals = scramble_values(mod)
        APP.processEvents()
        mod._signal_launcher.update_attribute_by_name.disconnect(check_fpga_value_equals_signal_value)
        # check that enough results have been received
        assert len(attr_names) <= len(self.results), \
            "%d attr_names > %d results"%(len(attr_names), len(self.results))
        # check that all values that were modified have returned at least one result
        resultnames = [name for (name, _, __) in self.results]
        for attr_name in attr_names:
            fullname = "%s.%s" % (mod.name, attr_name)
            assert fullname in resultnames, "%s not in resultnames"%fullname
        # check that the returned values are in agreement with our expectation
        exceptions = ['scope._reset_writestate_machine',  # always False
                      'asg0._offset_masked',  # TODO: migrate bit mask from #317
                      'asg1._offset_masked',  # set_value to validate_and_normalize #317
                      'asg0.offset',  # TODO: fix offset as named in issue #317
                      'asg1.offset',  # TODO: fix offset as named in issue #317
                      ]
        for (name, list_value, attr_value) in self.results:
            if not name in exceptions:
                assert (list_value == attr_value), (name, list_value, attr_value)
