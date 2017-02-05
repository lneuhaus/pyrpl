import logging
logger = logging.getLogger(name=__name__)
import os
from .. import *

class TestMemory(object):
    def test_load(self):
        mt = MemoryTree(filename='test', source='nosetests_source')
        assert mt is not None
        assert os.path.isfile(mt._filename)
        mt = MemoryTree()
        assert mt is not None
        assert mt._filename is None
        mt = MemoryTree(source="nosetests_source")
        assert mt is not None
        assert mt._filename is None
        mt = MemoryTree('test')
        assert mt.redpitaya._data is not None
        mt = MemoryTree('test')
        os.remove(mt._filename)
        mt = MemoryTree('test')
        assert len(mt._keys()) == 0
        os.remove(mt._filename)
