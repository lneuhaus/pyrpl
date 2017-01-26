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
        self.lockbox.add_output()
        old_name = self.lockbox.output_names[-1]
        assert(hasattr(self.lockbox, old_name))
        old_len = len(self.lockbox.outputs)
        self.lockbox.remove_output(self.lockbox.outputs[-1])
        assert(len(self.lockbox.outputs)==old_len-1)
        assert not (hasattr(self.lockbox, old_name))
        APP.processEvents()
        assert len(widget.all_sig_widget.output_widgets)==old_len-1

    def test_rename_output(self):
        """
        Check whether renaming an output updates everything properly
        """
        widget = self.lockbox.create_widget()
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
        assert hasattr(self.lockbox, names[-1])

    """
    def test_delete_output(self):
        widget = self.lockbox.create_widget()
        self.lockbox.add_output()
        old_name = self.lockbox.output_names[-1]
        assert (hasattr(self.lockbox, old_name))
        old_len = len(self.lockbox.outputs)
        self.lockbox.remove_output(self.lockbox.outputs[-1])
        assert (len(self.lockbox.outputs) == old_len - 1)
        assert not (hasattr(self.lockbox, old_name))
        APP.processEvents()
        assert len(widget.all_sig_widget.output_widgets) == old_len - 1
    """
    """
    def test_rename_output(self):
        widget = self.lockbox.create_widget()
        output1 = self.lockbox.add_output()
        output2 = self.lockbox.add_output()
        try:
            self.lockbox.rename_output(output1, output2.name)
        except ValueError:
            pass
        else:
            assert (False)  # should be impossible to duplicate name of outputs

        output2.name = "foo"
        assert (hasattr(self.lockbox, 'foo'))

        self.lockbox.rename_output(output2, 'bar')
        assert (hasattr(self.lockbox, 'bar'))

        assert (output2.pid.owner == 'bar')
    """