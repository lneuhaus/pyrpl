import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from PyQt4 import QtCore, QtGui
from .test_base import TestPyrpl

APP = QtGui.QApplication.instance()


class TestLockbox(TestPyrpl):
    def setup(self):
        self.lockbox = self.pyrpl.lockbox

    def test_create_output(self):
        old_len = len(self.lockbox.outputs)

        widget = self.lockbox.create_widget()
        self.lockbox._add_output()

        assert len(self.lockbox.outputs)==old_len + 1

        APP.processEvents()

        assert len(widget.all_sig_widget.output_widgets) == old_len + 1

        self.lockbox._add_output()

        names = self.lockbox._output_names#[out.name for out in self.lockbox.outputs]
        assert len(set(names)) == len(names) # Make sure unique names are
        # created
        assert hasattr(self.lockbox, names[-1])

    def test_delete_output(self):
        widget = self.lockbox.create_widget()
        self.lockbox._remove_all_outputs()
        self.lockbox._add_output()
        self.lockbox._add_output()
        old_name = self.lockbox._output_names[-1]
        assert(hasattr(self.lockbox, old_name))
        old_len = len(self.lockbox.outputs)
        self.lockbox._remove_output(self.lockbox.outputs[-1])
        assert(len(self.lockbox.outputs) == old_len-1)
        assert not (hasattr(self.lockbox, old_name))
        APP.processEvents()
        assert len(widget.all_sig_widget.output_widgets) == old_len-1
        self.lockbox._remove_all_outputs()
        out1 = self.lockbox._add_output()
        out = self.lockbox._add_output()
        self.lockbox.default_sweep_output = out
        self.lockbox._remove_output(out.name)
        # APP.processEvents()
        assert(self.lockbox.default_sweep_output == out1.name)

    def test_rename_output(self):
        """
        Check whether renaming an output updates everything properly
        """
        widget = self.lockbox.create_widget()
        self.lockbox._remove_all_outputs()
        output1 = self.lockbox._add_output()
        output2 = self.lockbox._add_output()
        try:
            self.lockbox._rename_output(output1, output2.name)
        except ValueError:
            pass
        else:
            assert(False) # should be impossible to duplicate name of outputs

        output2.name = "foo"
        assert(hasattr(self.lockbox, 'foo'))

        self.lockbox._rename_output(output2, 'bar')
        assert (hasattr(self.lockbox, 'bar'))

        assert(output2.pid.owner=='bar')

    def test_create_stage(self):
        old_len = len(self.lockbox._sequence.stages)
        widget = self.lockbox.create_widget()
        self.lockbox._add_stage()
        assert len(self.lockbox._sequence.stages) == old_len + 1

        APP.processEvents()

        assert len(widget.sequence_widget.stage_widgets) == old_len + 1

        self.lockbox._add_stage()

        names = self.lockbox._stage_names  # [out.name for out in self.lockbox.outputs]
        assert len(set(names)) == len(names)  # Make sure unique names are created
        assert hasattr(self.lockbox._sequence, names[-1])

    def test_delete_stage(self):
        widget = self.lockbox.create_widget()
        self.lockbox._add_stage()
        old_name = self.lockbox._stage_names[-1]
        assert (hasattr(self.lockbox._sequence, old_name))
        old_len = len(self.lockbox._sequence.stages)
        self.lockbox._remove_stage(self.lockbox._sequence.stages[-1])
        assert (len(self.lockbox._sequence.stages) == old_len - 1)
        assert not (hasattr(self.lockbox._sequence, old_name))
        APP.processEvents()
        assert len(widget.sequence_widget.stage_widgets) == old_len - 1

    def test_rename_stage(self):
        widget = self.lockbox.create_widget()
        stage1 = self.lockbox._add_stage()
        stage2 = self.lockbox._add_stage()
        try:
            self.lockbox._rename_stage(stage1, stage2.name)
        except ValueError:
            pass
        else:
            assert (False)  # should be impossible to duplicate name of outputs

        stage2.name = "foo"
        assert (hasattr(self.lockbox._sequence, 'foo'))

        self.lockbox._rename_stage(stage2, 'bar')
        assert (hasattr(self.lockbox._sequence, 'bar'))

    def test_real_lock(self):
        delay = 0.01
        pid = self.pyrpl.rp.pid1
        pid.i = 0.1
        pid.p = 0.1
        self.lockbox.classname = 'Linear'
        self.lockbox = self.pyrpl.lockbox  # not so beautiful but necessary because lockbox object was replaced
        self.lockbox._remove_all_stages()
        self.lockbox._remove_all_outputs()
        stage = self.lockbox._add_stage()
        out = self.lockbox._add_output()
        out.p = 0
        out.i = -10.
        stage.output_on = {"output1": (True, True, 1)}
        self.lockbox.linear_input.input_channel = 'pid1'
        out.output_channel = 'out1'
        pid.input = 'out1'
        stage.input = self.lockbox.linear_input
        stage.variable_value = 0.1
        self.lockbox.lock()
        APP.processEvents()
        mean, std = self.pyrpl.rp.sampler.mean_stddev('out1', delay)
        assert (mean > 0.5), mean  # since out1 should start at 1 V
        time.sleep(1.5)
        mean, std = self.pyrpl.rp.sampler.mean_stddev('pid1', delay)
        assert (abs(mean-0.1) < 0.01), mean
        assert (std < 0.01)
        mean, std = self.pyrpl.rp.sampler.mean_stddev('out1', delay)
        assert (abs(mean) < 0.01), mean
        assert (std < 0.01), std
