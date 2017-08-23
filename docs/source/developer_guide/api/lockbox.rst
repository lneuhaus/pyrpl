Lockbox
*********

Lockbox is the base class for all customizations of lockbox behavior.
Any customized lockbox is implemented by defining a class that inherits
from Lockbox. This allows to add custom functionality to preexisting
lockbox types and furthermore to easily overwrite the default functions
of the lockbox API with custom behaviour.

The general way to implement a custom lockbox class is to copy the file
"pyrpl/software\_modules/lockbox/models/custom\_lockbox\_example.py"
into the folder
"`:math:`PYRPL_USER_DIR` <https://github.com/lneuhaus/pyrpl/wiki/Installation:-Directory-for-user-data-%22PYRPL_USER_DIR%22>`__/lockbox"
and to start modifying it. PyRPL will automatically search this
directory for classes that have Lockbox as one base class and allow to
select these by setting the corresponding class name in the property
'classname' of a Lockbox instance.

Each time the Lockbox type is changed in this way, (can happen through
the API, the GUI or the configfile, i.e.
``pyrpl.lockbox.classname = 'FabryPerot'``), a new Lockbox object is
created from the corresponding derived class of Lockbox. This ensures
that the Lockbox and all its signals are properly initialized.

To keep the API user-friendly, two things should be done - since Lockbox
inherits from SoftwareModule, we must keep the namespace in this object
minimum. That means, we should make a maximum of properties and methods
hidden with the underscore-trick.

-  the derived Lockbox object should define a shortcut class object 'sc'
   that contains the most often used functions.

The default properties of Lockbox are

-  inputs: list or dict of inputs ---> a list is preferable if we want
   the input name to be changeable, otherwise the "name" property
   becomes redundant with the dict key. But maybe we actually want the
   signal names to be defined in the Lockbox class itself?

-  outputs: list or dict of outputs ---> same choice to make

-  function lock(setpoint, factor=1) ---> Needs to be well documented:
   for instance, I guess setpoint only applies to last stage and factor
   to all stages ? ---> Also, regarding the discussion about the return
   value of the function, I think you are right that a promise is
   exactly what we need. It can be a 5 line class with a blocking get()
   method and a non-blocking ready() method. We should use the same
   class for the method run.single() of acquisition instruments.

-  function unlock()

-  function sweep()

-  function calibrate() --> I guess this is a blocking function ?

-  property islocked

-  property state

---> Sequence (Stages) are missing in this list. I would advocate for
keeping a "sequence" container for stages since it can be desirable to
only manipulate the state of this submodule (especially with the new
YmlEditor, editing the sequence alone becomes a very natural thing to
do). I agree that the current implementation where all the sequence
management functions are actually delegated to Lockbox is garbage.

---> Now that we are at the point where one only needs to derive Lockbox
(which I believe makes sense), we could also simplify our lives by
making both the list of inputs and outputs fixe sized: they would both
be specified by a list-of-class in the LockboxClass definition. If the
names are also static, then it would probably be a list of tuples (name,
SignalClass) or an OrderedDict(name, SignalClass). I guess adding a
physical output is rare enough that it justifies writing a new class?

PS: regarding the specification of the pairs (name, signal) in the
Lockbox class. I just realized that if we want the lists to be
fixe-sized, the cleanest solution is to use a descriptor per input (same
for outputs). This is exactly what they are made for...

@Samuel: What is the advantage of your solution to saving inputs and
outputs as (Ordered)Dicts?
