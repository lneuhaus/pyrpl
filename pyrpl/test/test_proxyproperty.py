import logging
logger = logging.getLogger(name=__name__)
from .test_base import TestPyrpl
from ..modules import Module
from ..attributes import FloatProperty, SelectProperty, ProxyProperty
from ..module_attributes import *


class MySubModule(Module):
    myfloat = FloatProperty(min=-1e10, max=1e10, default=12.3)
    myselect = SelectProperty(options=[1,2,3,'a','b','c'], default='a')


class MyModule(Module):
    moduleproperty = ModuleProperty(MySubModule)
    myfloatproxy = ProxyProperty("moduleproperty.myfloat")
    myselectproxy = ProxyProperty("moduleproperty.myselect")
    myfloat = FloatProperty(min=-1e10, max=1e10, default=12.3)


class TestProxyProperty(TestPyrpl):
    def test_proxy(self):
        self.parent = self.pyrpl
        self.c = self.pyrpl.c
        m = MyModule(parent=self, name='m')

        # float proxy
        assert m.myfloat == 12.3
        assert m.myfloat == m.myfloatproxy
        m.myfloatproxy = 5.0
        # behaves lika a normal attribute
        assert m.myfloatproxy == 5.0
        # setting the proxy affects the underlying attribute
        assert m.moduleproperty.myfloat == 5.0
        # setting the underlying attribute affects the proxy
        m.moduleproperty.myfloat = 4.0
        assert m.myfloatproxy == 4.0

        # select proxy
        assert m.myselectproxy == 'a'
        assert m.myselectproxy == m.moduleproperty.myselect
        m.myselectproxy = 1
        assert m.myselectproxy == 1
        assert m.moduleproperty.myselect == 1
        m.moduleproperty.myselect = 3
        assert m.myselectproxy == 3
        assert m.moduleproperty.myselect == 3
        # options
        defaultoptions = [1,2,3,'a','b','c']
        newoptions = [5, 6, 7]

        # argument None:
        # select property
        options = m.moduleproperty.__class__.myselect.options(None).keys()
        assert options == defaultoptions, options
        # proxy
        options = m.__class__.myselectproxy.options(None).keys()
        assert options == defaultoptions, options
        # argument instance
        # select property
        options = m.moduleproperty.__class__.myselect.options(m.moduleproperty).keys()
        assert options == defaultoptions, options
        # proxy
        options = m.__class__.myselectproxy.options(m).keys()
        assert options == defaultoptions, options

        # change of options assuming that proxy is a SelectProperty of target module
        m.__class__.myselectproxy.change_options(m, newoptions)

        # argument None:
        # select property
        options = m.moduleproperty.__class__.myselect.options(None).keys()
        assert options == newoptions, options
        # proxy
        options = m.__class__.myselectproxy.options(None).keys()
        assert options == newoptions, options
        # argument instance
        # select property
        options = m.moduleproperty.__class__.myselect.options(m.moduleproperty).keys()
        assert options == newoptions, options
        # proxy
        options = m.__class__.myselectproxy.options(m).keys()
        assert options == newoptions, options

        # unfortunately, we do not know how to make this work:
        #assert isinstance(m.__class__.myselectproxy, SelectProperty)
        # instead, we have however a nice representation string
        repr = m.__class__.myselectproxy.__repr__()
        assert "SelectProperty" in repr, repr
