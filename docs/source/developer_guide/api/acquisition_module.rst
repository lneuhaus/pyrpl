AcquisitionModule
*******************


A proposal for a uniformized API for acquisition modules (Scope, SpecAn, NA)
============================================================================

Acquisition modules have 2 modes of operation: the synchronous (or
blocking) mode, and the asynchronous (or non-blocking mode). The curves
displayed in the graphical user interface are based on the asynchronous
operation.

Synchronous mode:
-----------------

The working principle in synchronous mode is the following:

1. setup(\*\*kwds): kwds can be used to specify new attribute values
   (otherwise, the current values are used)
2. (optional) curve\_ready(): returns True if the acquisition is
   finished, False otherwise.
3. curve(timeout=None): returns a curve (numpy arrays). The function
   only returns when the acquisition is done, or a timeout occurs. The
   parameter timeout (only available for scope and specan) has the
   following meaning:

   timeout>0: timeout value in seconds

   timeout<=0: returns immediately the current buffer without checking
   for trigger status.

   timeout is None: timeout is auto-set to twice the normal curve
   duration

No support for averaging, or saving of curves is provided in synchronous
mode

Asynchronous mode
-----------------

The asynchronous mode is supported by a sub-object "run" of the module.
When an asynchronous acquisition is running and the widget is visible,
the current averaged data are automatically displayed. Also, the run
object provides a function save\_curve to store the current averaged
curve on the hard-drive.

The full API of the "run" object is the following.

public methods (All methods return immediately)
-----------------------------------------------

-  single(): performs an asynchronous acquisition of avg curves. The
   function returns a promise of the result: an object with a ready()
   function, and a get() function that blocks until data is ready.
-  continuous(): continuously acquires curves, and performs a moving
   average over the avg last ones.
-  pause(): stops the current acquisition without restarting the
   averaging
-  stop(): stops the current acquisition and restarts the averaging.
-  save\_curve(): saves the currently averaged curve (or curves for
   scope)
-  curve(): the currently averaged curve

Public attributes:
------------------

-  curve\_name: name of the curve to create upon saving
-  avg: number of averages (not to confuse with averaging per point)
-  data\_last: array containing the last curve acquired
-  data\_averaged: array containing the current averaged curve
-  current\_average: current number of averages

---> I also wonder if we really want to keep the
running\_state/running\_continuous property (will be uniformized) inside
the \_setup\_attribute. Big advantage: no risk of loading a state with a
continuous acquisition running without noticing/big disadvantage:
slaving/restoring a running module would also stop it...
