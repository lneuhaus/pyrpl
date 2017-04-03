import logging
logger = logging.getLogger(name=__name__)
import os
from ..memory import MemoryTree, MemoryBranch
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
        assert mt.pyrpl._data is not None
        mt = MemoryTree('test')
        os.remove(mt._filename)
        mt = MemoryTree('test')
        assert len(mt._keys()) == 0
        os.remove(mt._filename)

    def test_usage(self):
        filename = 'test2'
        m = MemoryTree(filename)
        m.a = 1
        assert not isinstance(m.a, MemoryBranch)
        m.b = {}
        assert isinstance(m.b, MemoryBranch)
        m.b = 'fdf'
        assert not isinstance(m.b, MemoryBranch)
        m.c = []
        assert isinstance(m.c, MemoryBranch)
        m.c[0] = 0
        m.c[1] = 2
        assert m.c._pop(-1) == 2
        assert len(m.c) == 1
        m.c[1] = 11
        m.c[2] = 22
        m.c[3] = 33
        assert len(m.c) == 4
        assert m.c._pop(2) == 22
        assert m.c[2] == 33
        # do something tricky
        m.d = dict(e=1,
                   f=dict(g=[0, dict(h=[0,99,98]),{}]))
        assert m.d.f.g[1].h[2]==98
        assert isinstance(m.d.f.g[1].h, MemoryBranch)
        # list addition
        m.x = [1.2]
        assert (m.x+[2.1]) == [1.2, 2.1]
        assert ([3.2]+m.x) == [3.2, 1.2]
        # list addition with strings - used to be a source of bugs
        m.l = ['memory']
        assert (m.l+['list']) == ["memory", "list"]
        assert (['list']+m.l) == ["list", "memory"]
        # read from saved file
        m._save_now()
        m2 = MemoryTree(m._filename)
        assert m.d.f.g[1].h[2] == 98
        assert isinstance(m.d.f.g[1].h, MemoryBranch)
        # save and delete file
        m._save_now()
        os.remove(m._filename)
