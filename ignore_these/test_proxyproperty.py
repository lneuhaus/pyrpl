import logging
logger = logging.getLogger(name=__name__)
from pyrpl.modules import Module
from pyrpl.attributes import FloatProperty, SelectProperty, ProxyProperty
from pyrpl.module_attributes import *
from pyrpl.memory import MemoryTree
from pyrpl.async_utils import sleep


class MySubModule(Module):
    myfloat = FloatProperty(min=-1e10, max=1e10, default=12.3)
    myselect = SelectProperty(options=[1,2,3,'a','b','c'], default='a')


class MyModule(Module):
    moduleproperty = ModuleProperty(MySubModule)
    myfloatproxy = ProxyProperty("moduleproperty.myfloat", call_setup=True)
    myselectproxy = ProxyProperty("moduleproperty.myselect")
    myfloat = FloatProperty(min=-1e10, max=1e10, default=12.3)

    def _setup(self):
        self.setup_called = True

class SignalReceiver(object):
    """
    slots for signals to ensure that signals are properly emitted
    """
    def update_attribute_by_name(self, name, value):
        self.arrived_signal = (name, value)

    def change_options(self, name, options):
        self.arrived_signal = (name, options)

    def change_ownership(self):
        self.arrived_signal = True


class TestProxyProperty(object):
    def test_proxy(self):
        self.pyrpl = None
        self.parent = self.pyrpl
        self.c = MemoryTree()
        m = MyModule(parent=self, name='m')

        assert m.__class__.myselectproxy.name == 'myselectproxy'

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

        m.setup_called = False
        assert not m.setup_called
        m.moduleproperty.myfloat = 2.0
        assert m.setup_called

        m.setup_called = False
        assert not m.setup_called
        m.myfloatproxy = 3.0
        assert m.setup_called

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
        options = list(m.moduleproperty.__class__.myselect.options(None).keys())
        assert options == defaultoptions, options
        # proxy
        options = list(m.__class__.myselectproxy.options(None).keys())
        assert options == defaultoptions, options
        # argument instance
        # select property
        options = list(m.moduleproperty.__class__.myselect.options(m.moduleproperty).keys())
        assert options == defaultoptions, options
        # proxy
        options = list(m.__class__.myselectproxy.options(m).keys())
        assert options == defaultoptions, options

        # change of options assuming that proxy is a SelectProperty of target module
        m.__class__.myselectproxy.change_options(m, newoptions)
        # argument None:
        # select property
        options = list(m.moduleproperty.__class__.myselect.options(None).keys())
        assert options == newoptions, options
        # proxy
        options = list(m.__class__.myselectproxy.options(None).keys())
        assert options == newoptions, options
        # argument instance
        # select property
        options = list(m.moduleproperty.__class__.myselect.options(m.moduleproperty).keys())
        assert options == newoptions, options
        # proxy
        options = list(m.__class__.myselectproxy.options(m).keys())
        assert options == newoptions, options

        # unfortunately, we do not know how to make this work:
        #assert isinstance(m.__class__.myselectproxy, SelectProperty)
        # instead, we have however a nice representation string
        repr = m.__class__.myselectproxy.__repr__()
        assert "SelectProperty" in repr, repr

        # connect slots to signals of this module
        s = SignalReceiver()
        m._signal_launcher.connect_widget(s)

        # setup and perform some action
        s.arrived_signal = False
        m.myselectproxy = 7
        # see whether signal arrives
        for i in range(100):
            sleep(0.01)
            if s.arrived_signal:
                break
        else:
            assert False, "Timeout: proxy signals are not properly connected"
        assert s.arrived_signal == ("myselectproxy", [7]), s.arrived_signal

        assert m.myselectproxy_options == newoptions

        # setup and perform some action
        s.arrived_signal = False
        m.__class__.myselectproxy.change_options(m, ['foo', 'par'])
        # see whether signal arrives
        for i in range(100):
            sleep(0.01)
            if s.arrived_signal:
                break
        else:
            assert False, "Timeout: proxy signals are not properly connected"
        assert s.arrived_signal == ("myselectproxy", ['foo', 'par']), \
            s.arrived_signal

        assert m.myselectproxy_options == ['foo', 'par']
