import logging

import pytest

from pyrpl.software_modules.module_managers import ModuleManager
from pyrpl.test.test_base import TestPyrpl

# passes on the simulated (_FAKE_) Red Pitaya too
pytestmark = pytest.mark.simulation

logger = logging.getLogger(name=__name__)


class TestOwnership(TestPyrpl):
    def test_ownership_restored(self):
        # make sure scope rolling_mode and running states are correctly setup
        # when something is changed
        if self.r is None:
            return
        self.pyrpl.networkanalyzer.iq.free()
        # otherwise not a single iq is left for test

        self.r.asg0.free()
        # otherwise not a single asg is left for test

        for module in self.pyrpl.modules:
            if isinstance(module, ModuleManager):
                with module.pop("foo") as mod:
                    assert mod.owner == "foo"
                assert mod.owner is None
