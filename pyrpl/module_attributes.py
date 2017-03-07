from .attributes import *
from .modules import *


# # basic ModuleAttribute object is imported from attributes
# class ModuleAttribute(BaseAttribute):
#     def __init__(self, module_cls, default=None, doc="", ignore_errors=False):
#         self.module_cls = module_cls
#         super(ModuleAttribute, self).__init__(default=default, doc=doc,
#                                               ignore_errors=ignore_errors)


class ModuleProperty(ModuleAttribute, BaseProperty):
    """
    A property for a submodule.
    """
    default = {}
    def set_value(self, obj, val):
        """
        Use the dictionnary val to set_setup_attributes
        :param obj:
        :param val:
        :return:
        """
        getattr(obj, self.name).setup_attributes = val
        return val


class ModuleList(list, SoftwareModule):
    """ a list of modules"""
    def __init__(self, parent, element_cls, initlist=[]):
        self.parent = parent
        self.element_cls = element_cls
        super(ModuleList, self).__init__([])
        self.extend(initlist)

    # all read-only methods from the base class 'list' work perfectly well for us, i.e.
    # __getitem__, count(), index(), reverse()

    def __setitem__(self, index, value):
        # setting a list element sets up the corresponding module
        self[index].setup_attributes = value

    def insert(self, index, new):
        # make new module
        to_add = self.element_cls(self.parent)
        # initialize setup_attributes
        to_add.setup_attributes = new
        # insert into list
        super(ModuleList, self).insert(index, to_add)

    def append(self, new):
        self.insert(-1, new)

    def extend(self, iterable):
        for i in iterable:
            self.append(i)

    def __delitem__(self, index):
        # setting a list element sets up the corresponding module
        to_delete = super(ModuleList, self).pop(index)
        # call destructor
        to_delete._clear()

    def pop(self, index=-1):
        # get attributes
        setup_attributes = self[index].setup_attributes
        self.__delitem__(index)
        return setup_attributes

    def remove(self, value):
        self.__delitem__(self.index(value))

    @property
    def setup_attributes(self):
        return [item.setup_attributes for item in self]


class ModuleListProperty(BaseAttribute):
    """
    A property for a list of submodules.
    """
    default = [{}]
    module_cls = ModuleList

    def __init__(self, element_cls, default=None, doc="", ignore_errors=False):
        self.element_cls = element_cls
        super(ModuleListProperty, self).__init__(default=default, doc=doc,
                                                 ignore_errors=ignore_errors)

    def get_value(self, obj, obj_type):
        if not hasattr(obj, '_' + self.name):
            setattr(obj, '_' + self.name, self.module_cls(obj, self.element_cls, self.default))
        return getattr(obj, '_' + self.name)

    def set_value(self, obj, val):
        modulelist = getattr(obj, self.name)
        for i, v in enumerate(val):
            try:
                modulelist[i] = v
            except IndexError:
                modulelist.append(v)
        while len(modulelist) > len(val):
            modulelist.remove(-1)

    def validate_and_normalize(self, value, obj):
        if not isinstance(value, list):
            try:
                value = value.values()
            except AttributeError:
                raise ValueError("ModuleProperty must be assigned a list. You have wrongly assigned an object of type "
                                 "%s. ", type(value))
        return value


class ModuleContainerProperty(ModuleProperty):
    default_module_cls = SoftwareModule
    def __init__(self, module_cls=None, default=None, doc="",
                 ignore_errors=False, **kwargs):
        """ returns a descriptor for a module container, i.e. a class that contains submodules whose name and class are
        specified in kwargs. module_cls is the base class for the module container (typically SoftwareModule)"""
        # we simply create a container class that loosely resembles a dictionary which contains the given submodules
        if module_cls is None:
            module_cls = self.default_module_cls
        class ModuleContainer(module_cls):
            def __getitem__(self, key):
                return getattr(self, key)
            def keys(self):
                return self._module_attributes
            def values(self):
                return [self[k] for k in self.keys()]
            def items(self):
                return [(k, self[k]) for k in self.keys()]
            def __iter__(self):
                # this method allows to write code like this: 'for submodule in modulecontainer: submodule.do_sth()'
                return iter(self.values())
            # add the submodule entries here such that the metaclass of module_cls can do its job
            for k, v in kwargs.items():
                locals()[k] = ModuleProperty(v)
            # this re-definition essentially silences the warning issued
            # when nonexisting submodules are present in the config file
            @property
            def setup_attributes(self):
                return module_cls.setup_attributes
            @setup_attributes.setter
            def setup_attributes(self, kwds):
                module_cls.setup_attributes = \
                    {k:v for k, v in kwds.items() if k in self._setup_attributes}

        super(ModuleContainerProperty, self).__init__(ModuleContainer, default=default,
                                                      doc=doc, ignore_errors=ignore_errors)
