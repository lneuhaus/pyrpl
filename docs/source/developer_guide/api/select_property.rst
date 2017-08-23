Starting to rewrite SelectAttribute/Property
*********************************************


Guidelines: - Options must not be a bijection any more, but can be only
an injection (multiple keys may correspond to the same value). - Options
can be given as a dict, an OrderedDict, a list (only for properties -
automatically converted into identity ordereddict), or a callable object
that takes 1 argument (instance=None) and returns a list or a dict. -
Options can be changed at any time, and a change of options should
trigger a change of the options in the gui. - Options should be provided
in the right order (no sorting is performed in order to not mess up the
predefined order. Use pyrpl\_utils.sorted\_dict() to sort you options if
you have no other preferrence.

-  The SelectProperty should simply save the key, and not care at all
   about the value.
-  Every time a set/get operation is performed, the following things
   should be confirmed:
-  the stored key is a valid option
-  in case of registers: the stored value corresponds to the stored key.
   if not: priority is given to the key, which is set to make sure that
   value/key correspond. Still, an error message should be logged.
-  if eventually, the key / value does not correspond to anything in the
   options, an error message should be logged. the question is what we
   should do in this case:

a) keep the wrong key -> means a SelectRegister does not really fulfill
   its purpose of selecting a valid options
b) issue an error and select the default value instead -> better

Default value: - self.default can be set to a custom default value (at
module initialization), without having to comply with the options. - the
self.default getter will be obliged to return a valid element of the
options list. that is, it will first try to locate the overwritten
default value in the options. if that fails, it will try to return the
first option. if that fails, too, it will return None
