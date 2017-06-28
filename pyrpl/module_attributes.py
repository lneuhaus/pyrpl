from .attributes import *
from .modules import *


class ModuleProperty(ModuleAttribute):
    """
    A property for a submodule.

    The ModuleAttribute is declared with:
    ModuleAttribute(module_cls, default, doc)

    The module_cls is instantiated in the __init__ of the parent module

    For the moment, the following actions are supported:
       - module.sub = dict(...) : module.sub.set_setup_attributes(dict(...))
       - module.sub: returns the submodule.
    """
    default = {}

    def __init__(self,
                 module_cls,
                 default=None,
                 doc="",
                 ignore_errors=False,
                 call_setup=False,
                 **kwargs):
        self.module_cls = module_cls
        self.kwargs = kwargs
        ModuleAttribute.__init__(self,
                               default=default,
                               doc=doc,
                               ignore_errors=ignore_errors,
                               call_setup=call_setup)

    def set_value(self, obj, val):
        """
        Use the dictionnary val to set_setup_attributes
        :param obj:
        :param val:
        :return:
        """
        getattr(obj, self.name).setup_attributes = val
        return val

    def get_value(self, obj):
        if not hasattr(obj, '_' + self.name):
            # getter must manage the instantiation of default value
            setattr(obj, '_' + self.name,
                self._create_module(obj))
        return getattr(obj, '_' + self.name)

    def _create_module(self, obj):
        return self.module_cls(obj, name=self.name, **self.kwargs)


class ModuleList(Module, list):
    """ a list of modules"""
    def __init__(self, parent, name=None, element_cls=Module, default=[]):
        def element_name(element_self):
            """ function that is used to dynamically assign each
            ModuleListElement's name to the index in the list.
            This is needed for proper storage in the config file"""
            try:
                return element_self.parent.index(element_self)
            except ValueError:
                return element_self._initial_name #'not in list' #return len(element_self.parent)
        def element_next(element_self):
            try:
                return element_self.parent[element_self.parent.index(element_self)+1]
            except:
                return None
        def element_init(element_self, parent, initial_name=None, *args, **kwargs):
            # creates a wrapper around the init function to pass the initial element
            # number in the list at object creation
            element_self._initial_name = initial_name
            return element_cls.__init__(element_self, parent, *args, **kwargs)
        # element.name equals element.number in order to get the right config
        # file section
        self.element_cls = type(element_cls.__name__ + "ListElement",
                                (element_cls, ),
                                {'name': property(fget=element_name),
                                 'next': property(fget=element_next),
                                 '__init__': element_init
                                })
        self._signal_launcher = self.element_cls._signal_launcher
        super(ModuleList, self).__init__(parent, name=name)
        # set to default setting
        self.extend(default)

    # all read-only methods from the base class 'list' work perfectly well for us, i.e.
    # __getitem__, count(), index(), reverse()
    def __setitem__(self, index, value):
        # setting a list element sets up the corresponding module
        self[index].setup_attributes = value

    def insert(self, index, new):
        # insert None as a placeholder at the right place in the list
        # in order to assign right indices to surrounding elements
        super(ModuleList, self).insert(index, None)
        # make new module (initial_name must be given).
        super(ModuleList, self).__setitem__(index,
                            self.element_cls(self, initial_name=index))
        # set initial name to none, since name is now inferred from index in the list
        self[index]._initial_name=None
        # initialize setup_attributes
        self[index].setup_attributes = new
        # save state
        self.save_state()

    def append(self, new):
        self.insert(self.__len__(), new)

    def extend(self, iterable):
        for i in iterable:
            self.append(i)

    def __delitem__(self, index=-1):
        # make sure at object destruction that the name variable corresponds to former name
        self[index]._initial_name = index
        # setting a list element sets up the corresponding module
        to_delete = super(ModuleList, self).pop(index)
        # call destructor
        to_delete._clear()
        # remove saved state from config file
        self.c._pop(index)
        #self.save_state()

    def pop(self, index=-1):
        # get attributes
        setup_attributes = self[index].setup_attributes
        self.__delitem__(index)
        return setup_attributes

    def remove(self, value):
        self.__delitem__(self.index(value))

    def __repr__(self):
        return str(ModuleList.__name__)+"("+list.__repr__(self)+")"

    @property
    def setup_attributes(self):
        return [item.setup_attributes for item in self]

    @setup_attributes.setter
    def setup_attributes(self, val):
        for i, v in enumerate(val):
            try:
                self[i] = v
            except IndexError:
                self.append(v)
        while len(self) > len(val):
            self.__delitem__(-1)

    def _load_setup_attributes(self):
        """
         Load and sets all setup attributes from config file
        """
        if self.c is not None:
            # self.c._data is a list that can be passed to setup_attributes
            self.setup_attributes = self.c._data


class ModuleListProperty(ModuleProperty):
    """
    A property for a list of submodules.
    """
    default = []
    module_cls = ModuleList

    def __init__(self, element_cls, default=None, doc="", ignore_errors=False):
        # only difference to base class: need to assign element_cls (i.e. class of element modules)
        self.element_cls = element_cls
        ModuleProperty.__init__(self,
                                self.module_cls,
                                default=default,
                                doc=doc,
                                ignore_errors=ignore_errors)

    def _create_module(self, obj):
        newmodule = self.module_cls(obj,
                                    name=self.name,
                                    element_cls=self.element_cls,
                                    default=self.default)
        try:
            newmodule._widget_class = self._widget_class
        except AttributeError:
            pass
        return newmodule

    def validate_and_normalize(self, obj, value):
        """ ensures that only list-like values are passed to the ModuleProperty """
        if not isinstance(value, list):
            try:
                value = value.values()
            except AttributeError:
                raise ValueError("ModuleProperty must be assigned a list. "
                                 "You have wrongly assigned an object of type "
                                 "%s. ", type(value))
        return value


class ModuleDict(Module):
    """
    container class that loosely resembles a dictionary which contains submodules
    """
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

    @property
    def setup_attributes(self):
        return super(ModuleDict, self).setup_attributes

    @setup_attributes.setter
    def setup_attributes(self, kwds):
        Module.setup_attributes.fset(self,
            {k: v for k, v in kwds.items() if k in self._setup_attributes})

    def __setitem__(self, key, value):
        # make the new ModuleProperty of module type "value" in the class
        mp = ModuleProperty(value)
        mp.name = key  # assign module name
        setattr(self.__class__, key, mp)
        # do what the constructor would do: append to setup_attributes...
        self._module_attributes.append(key)
        self._setup_attributes.append(key)
        # ... attribute the name
        self[key].name = key
        # initialize with saved values if available
        self[key]._load_setup_attributes()

    def __delitem__(self, key):
        self._module_attributes.pop(key)
        self._setup_attributes.pop(key)
        getattr(self, key)._clear()
        delattr(self, key)

    def pop(self, key):
        """ same as __delattr__ (does not return a value) """
        module = self._setup_attributes.pop(key)
        delattr(self, key)
        return module


class ModuleDictProperty(ModuleProperty):
    default_module_cls = Module

    def __init__(self, module_cls=None, default=None, doc="",
                 ignore_errors=False, **kwargs):
        """
        returns a descriptor for a module container, i.e. a class that contains submodules whose name and class are
        specified in kwargs. module_cls is the base class for the module container (typically SoftwareModule)
        """
        # get default base class to inherit from
        if module_cls is None:
            module_cls = self.default_module_cls
        # make a copy of ModuleDict class that can be modified without modifying all ModuleDict class instances
        # inherit from module_cls
        ModuleDictClassInstance = type(module_cls.__name__+"DictPropertyInstance",
                                       (ModuleDict, module_cls),
                    {key: ModuleProperty(value) for key, value in kwargs.items()})
        # metaclass of Module already takes care of _setup/module_attributes
        # and names of submodules, so no need for these two:
        # ModuleDictClassInstance._setup_attributes = kwargs.keys()
        # ModuleDictClassInstance._module_attributes = kwargs.keys()

        # init this attribute with the contained module
        super(ModuleDictProperty, self).__init__(ModuleDictClassInstance,
                                                 default=default,
                                                 doc=doc,
                                                 ignore_errors=ignore_errors)

