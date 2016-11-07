from nose.tools import with_setup
from unittest import TestCase
import os
import numpy as np
import logging
logger = logging.getLogger(name=__name__)

from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import *
from pyrpl.redpitaya_registers import *


class TestClass(object):
    @classmethod
    def setUpAll(self):
        pass


    def test_module_attributes(self):
        class DummyModule(SoftwareModule):
            gui_attributes = ['true_or_false']
            true_or_false = BoolProperty()

        d = DummyModule()
        assert(isinstance(d.true_or_false, bool))


    def test_software_module_widget(self):
        #if self.r is None:
        #    return

        class DummyModule(SoftwareModule):
            gui_attributes = ['true_or_false']
            true_or_false = BoolProperty()

        d = DummyModule()
        d.create_widget()