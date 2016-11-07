"""
Properties mimic the behavior of Registers: the internal value is simply stored as
module._property_name instead of being retrieved from the redpitaya.
"""

from pyrpl.attributes import SelectAttribute, StringAttribute, PhaseAttribute,\
                             IntAttribute, BoolAttribute, FloatAttribute, \
                             FrequencyAttribute, FilterAttribute
class BaseProperty(object):
    """
    A Property is a special type of attribute that is not mapping a fpga value, but rather an attribute _attr_name
    of the module. This is used mainly in SoftwareModules
    """

    def get_value(self, obj, obj_type):
        if obj is None:
            return self
        if not hasattr(obj, '_' + self.name):
            setattr(obj, '_' + self.name, self.default)
        return getattr(obj, '_' + self.name)

    def set_value(self, obj, val):
        setattr(obj, '_' + self.name, val)
        return val # maybe better with getattr... but more expensive


class SelectProperty(SelectAttribute, BaseProperty): pass


class StringProperty(StringAttribute, BaseProperty):
    default = ""


class PhaseProperty(PhaseAttribute, BaseProperty):
    default = 0

class FloatProperty(FloatAttribute, BaseProperty):
    default = 0.


class FrequencyProperty(FrequencyAttribute, BaseProperty):
    default = 0.


class LongProperty(IntAttribute, BaseProperty):
    def __init__(self, min=0, max=2**14, increment=1, doc=""):
        super(LongProperty, self).__init__(min=min, max=max, increment=increment, doc=doc)
    default = 0


class BoolProperty(BoolAttribute, BaseProperty):
    default = False

class FilterProperty(FilterAttribute, BaseProperty):
    default = 10