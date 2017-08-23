Base classes Attributes and Module
*************************************


Two concepts are central to almost any object in the API: Attributes and
Modules.

Attributes are essentially variables which are automatically
synchronized between a number of devices, i.e. the value of an FPGA
register, a config file to store the last setting on the harddisk, and
possibly a graphical user interface.

Modules are essentially collections of attributes that provide
additional functions to usefully govern the interaction of the available
attributes.

It is recommended to read the definition of these two classes, but we
summarize the way they are used in practice by listing the important
methods:

Module (see BaseModule in module.py)
====================================

A module is a component of pyrpl doing a specific task, such as e.g.
Scope/Lockbox/NetworkAnalyzer. The module can have a widget to interact
with it graphically.

It is composed of attributes (see attributes.py) whose values represent
the current state of the module (more precisely, the state is defined by
the value of all attributes in \_setup\_attributes)

The module can be slaved or freed by a user or another module. When the
module is freed, it goes back to the state immediately before being
slaved. To make sure the module is freed, use the syntax:

with pyrpl.mod\_mag.pop('owner') as mod: mod.do\_something()

public methods
--------------

-  get\_setup\_attributes(): returns a dict with the current values of
   the setup attributes
-  set\_setup\_attributes(\*\*kwds): sets the provided setup\_attributes
   (setup is not called)
-  save\_state(name): saves the current "state" (using
   get\_setup\_attribute) into the config file
-  load\_state(name): loads the state 'name' from the config file (setup
   is not called by default)
-  create\_widget(): returns a widget according to widget\_class
-  setup(\ **kwds): first, performs set\_setup\_attributes(**\ kwds),
   then calls \_setup() to set the module ready for acquisition. This
   method is automatically created by ModuleMetaClass and it combines
   the docstring of individual setup\_attributes with the docstring of
   \_setup()
-  free: sets the module owner to None, and brings the module back the
   state before it was slaved equivalent to module.owner = None)

Public attributes:
------------------

-  name: attributed based on \_section\_name at instance creation (also
   used as a section key in the config file)
-  states: the list of states available in the config file
-  owner: (string) a module can be owned (reserved) by a user or another
   module. The module is free if and only if owner is None
-  pyrpl: recursively looks through parent modules until it reaches the
   pyrpl instance

class attributes to be implemented in derived class:
----------------------------------------------------

-  individual attributes (instances of BaseAttribute)
-  \_setup\_attributes: attribute names that are touched by
   setup(\*\*kwds)/ saved/restored upon module creation
-  \_gui\_attributes: attribute names to be displayed by the widget
-  \_callback\_attributes: attribute\_names that triggers a callback
   when their value is changed in the base class, \_callback just calls
   setup()
-  \_widget\_class: class of the widget to use to represent the module
   in the gui(a child of ModuleWidget)
-  \_section\_name: the name under which all instances of the class
   should be stored in the config file

methods to implement in derived class:
--------------------------------------

-  \_init\_module(): initializes the module at startup. During this
   initialization, attributes can be initialized without overwriting
   config file values. Practical to use instead of **init** to avoid
   calling super().\ **init**\ ()
-  \_setup(): sets the module ready for acquisition/output with the
   current attribute's values. The metaclass of the module autogenerates
   a function like this: def setup(self, **kwds): **\ \* docstring of
   function \_setup *** *** for attribute in self.setup\_attributes:
   print-attribute-docstring-here \*\*\*\*

   ::

       self.set_setup_attributes(kwds)
       return self._setup()

-  \_ownership\_changed(old, new): this function is called when the
   module owner changes it can be used to stop the acquisition for
   instance.

Attributes
==========

The parameters of the modules are controlled by descriptors deriving
from BaseAttribute.

An attribute is a field that can be set or get by several means:

-  programmatically: module.attribute = value

-  graphically: attribute.create\_widget(module) returns a widget to
   manipulate the value

-  via loading the value in a config file for permanent value
   preservation

Attributes have a type (BoolAttribute, FloatAttribute...), and they are
actually separated in two categories:

-  Registers: the attributes that are stored in the FPGA itself

-  Properties: the attributes that are only stored in the computer and
   that are not representing an FPGA register

A common mistake is to use the Attribute class instead of the
corresponding Register or Property class (FloatAttribute instead of
FloatRegister or FloatProperty for instance): this class is abstract
since it doesn't define a set\_value/get\_value method to specify how
the data is stored in practice.
