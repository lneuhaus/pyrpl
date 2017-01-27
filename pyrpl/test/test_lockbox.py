import logging
logger = logging.getLogger(name=__name__)
import time
import numpy as np
from PyQt4 import QtCore, QtGui
from .test_base import TestPyrpl
APP = QtGui.QApplication.instance()


class TestClass(TestPyrpl):
    def setup(self):
        self.lockbox = self.pyrpl.lockbox
        self.extradelay = 0.6 * 8e-9  # no idea where this comes from

    def test_create_output(self):
        old_len = len(self.lockbox.outputs)

        widget = self.lockbox.create_widget()
        self.lockbox.add_output()

        assert len(self.lockbox.outputs)==old_len + 1

        APP.processEvents()

        assert len(widget.all_sig_widget.output_widgets) == old_len + 1

        self.lockbox.add_output()

        names = self.lockbox.output_names#[out.name for out in self.lockbox.outputs]
        assert len(set(names))==len(names) # Make sure unique names are created
        assert hasattr(self.lockbox, names[-1])

    def test_delete_output(self):
        widget = self.lockbox.create_widget()
        self.lockbox.remove_all_outputs()
        self.lockbox.add_output()
        self.lockbox.add_output()
        old_name = self.lockbox.output_names[-1]
        assert(hasattr(self.lockbox, old_name))
        old_len = len(self.lockbox.outputs)
        self.lockbox.remove_output(self.lockbox.outputs[-1])
        assert(len(self.lockbox.outputs)==old_len-1)
        assert not (hasattr(self.lockbox, old_name))
        APP.processEvents()
        assert len(widget.all_sig_widget.output_widgets)==old_len-1
        self.lockbox.remove_all_outputs()
        out1 = self.lockbox.add_output()
        out = self.lockbox.add_output()
        self.lockbox.default_sweep_output = out
        self.lockbox.remove_output(out.name)
        # APP.processEvents()
        assert(self.lockbox.default_sweep_output==out1.name)

    def test_rename_output(self):
        """
        Check whether renaming an output updates everything properly
        """
        widget = self.lockbox.create_widget()
        self.lockbox.remove_all_outputs()
        output1 = self.lockbox.add_output()
        output2 = self.lockbox.add_output()
        try:
            self.lockbox.rename_output(output1, output2.name)
        except ValueError:
            pass
        else:
            assert(False) # should be impossible to duplicate name of outputs

        output2.name = "foo"
        assert(hasattr(self.lockbox, 'foo'))

        self.lockbox.rename_output(output2, 'bar')
        assert (hasattr(self.lockbox, 'bar'))

        assert(output2.pid.owner=='bar')

    def test_create_stage(self):
        old_len = len(self.lockbox.sequence.stages)
        widget = self.lockbox.create_widget()
        self.lockbox.add_stage()
        assert len(self.lockbox.sequence.stages) == old_len + 1

        APP.processEvents()

        assert len(widget.sequence_widget.stage_widgets) == old_len + 1

        self.lockbox.add_stage()

        names = self.lockbox.stage_names  # [out.name for out in self.lockbox.outputs]
        assert len(set(names)) == len(names)  # Make sure unique names are created
        assert hasattr(self.lockbox.sequence, names[-1])

    def test_delete_stage(self):
        widget = self.lockbox.create_widget()
        self.lockbox.add_stage()
        old_name = self.lockbox.stage_names[-1]
        assert (hasattr(self.lockbox.sequence, old_name))
        old_len = len(self.lockbox.sequence.stages)
        self.lockbox.remove_stage(self.lockbox.sequence.stages[-1])
        assert (len(self.lockbox.sequence.stages) == old_len - 1)
        assert not (hasattr(self.lockbox.sequence, old_name))
        APP.processEvents()
        assert len(widget.sequence_widget.stage_widgets) == old_len - 1

    def test_rename_stage(self):
        widget = self.lockbox.create_widget()
        stage1 = self.lockbox.add_stage()
        stage2 = self.lockbox.add_stage()
        try:
            self.lockbox.rename_stage(stage1, stage2.name)
        except ValueError:
            pass
        else:
            assert (False)  # should be impossible to duplicate name of outputs

        stage2.name = "foo"
        assert (hasattr(self.lockbox.sequence, 'foo'))

        self.lockbox.rename_stage(stage2, 'bar')
        assert (hasattr(self.lockbox.sequence, 'bar'))

    def test_real_lock(self):
        pid = self.pyrpl.rp.pid1
        pid.i = 0.1
        pid.p = 0.1
        self.lockbox.remove_all_stages()
        self.lockbox.remove_all_outputs()
        self.lockbox.model_name = 'Linear'
        stage = self.lockbox.add_stage()
        out = self.lockbox.add_output()
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
        mean, std = self.pyrpl.rp.sampler.mean_stddev('out1', 0.01)
        assert (mean>0.9) # since out1 should start at 1 V
        time.sleep(1.5)
        mean, std = self.pyrpl.rp.sampler.mean_stddev('pid1', 0.01)
        assert (abs(mean-0.1)<0.01)
        assert (std<0.01)
        mean, std = self.pyrpl.rp.sampler.mean_stddev('out1', 0.01)
        assert (abs(mean) < 0.01)
        assert (std<0.01)
