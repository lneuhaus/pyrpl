Asynchronous sleep function and benchmarks
***********************************************************************

An asynchronous sleep function is highly desirable to let the GUI loop
(at the moment, the Qt event loop) run while pyrpl is waiting for curves
from the instruments.

The benchmark can be found in :download:`timers.ipynb`. It was
executed on python 3.5 on a windows 10 anaconda system.


Methods compatible with python 2:
==================================

We first compare 4 different implementations of the sleep function that
are all fully compatible between python 2 and python 3.

The normal time.sleep function (which is not asynchronous)
----------------------------------------------------------

Calling time.sleep(delays) with delays ranging continuously from 0 to 5
ms gives the following distribution of measured delay vs requested
delay:

.. figure:: images/without_timer/time.sleep.png
   :alt: 

As stated in the doc, sleep never returns before the requested delay,
however, it will try its best not to return more than 1 ms too late.
Moreover, we clearly have a problem because no qt events will be
processed since the main thread is blocked by the current execution of
time.sleep: for instance a timer's timeout will only be triggered once
the sleep function has returned, this is what's causing freezing of the
GUI when executing code in the jupyter console.

Constantly calling APP.processEvents()
--------------------------------------

The first work around, is to manually call processEvents() regularly to
make sure events are processed while our process is sleeping.

::

    from timeit import default_timer

    def sleep_pe(delay):
        time0 = default_timer()
        while(default_timer()<time0+delay):
            APP.processEvents()

first comment: we need to use timit.default\_timer because time.time has
also a precision limited to the closest millisecond.

.. figure:: images/without_timer/processEvents.png
   :alt: 

We get, as expected, an almost perfect correlation between requested
delays and obtained delays. Some outliers probably result from the OS
interrupting the current process execution, or even other events from
the GUI loop being executed just before the requested time.

We also see that the CPU load is quite high, even though we don't do
anything but waiting for events. This is due to the loop constantly
checking for the current time and comparing it to the requested delay.

Running the QEventLoop locally
------------------------------

A better solution, as advertised
`here <https://doc.qt.io/archives/qq/qq27-responsive-guis.html#waitinginalocaleventloop>`__,
is to run a new version of the QEventLoop locally:

::

    def sleep_loop(delay):
       loop = QtCore.QEventLoop()
       timer = QtCore.QTimer()
       timer.setInterval(delay*1000)
       timer.setSingleShot(True)
       timer.timeout.connect(loop.quit)
       timer.start()
       loop.exec() # la loop prend en charge elle-même l'évenement du timer qui va la faire mourir après delay.

The subtlety here is that the loop.exec() function is blocking, and
usully would never return. To force it to return after some time delay,
we simply instanciate a QTimer and connect its timeout signal to the
quit function of the loop. The timer's event is actually handled by the
loop itself. We then get a much smaller CPU load, however, we go back to
the situation where the intervals are only precise at the nearest
millisecond.

.. figure:: images/without_timer/qeventloop.png
   :alt: 


The hybrid approach
-------------------

A compromise is to use a QTimer that will stop 1 ms earlier, and then
manually call processEvents for the remaining time. We get at the same
time a low CPU load (as long as delay >> 1 ms, which is not completely
verified here), and a precise timing.

::

    def my_sleep(delay):
        tic = default_timer()
        if delay>1e-3:
            sleep_loop(delay - 1e-3)
        while(default_timer()<tic+delay):
            APP.processEvents()

.. figure:: images/without_timer/my_sleep.png
   :alt: 


Benchmark in the presence of other events
-----------------------------------------

To simulate the fact that in real life, other events have to be treated
while the loop is running (for instance, user interactions with the GUI,
or another instrument running an asynchronous measurement loop), we run
in parallel the following timer:

::

    from PyQt4 import QtCore, QtGui
    n_calc = [0]
    def calculate():
        sin(rand(1000))
        n_calc[0]+=1
        timer.start()

    timer = QtCore.QTimer()
    timer.setInterval(0)
    timer.setSingleShot(True)
    timer.timeout.connect(calculate)

By looking at how fast ``n_calc[0]`` gets incremented, we can measure
how blocking our sleep-function is for other events. We get the
following outcomes (last number "calc/s" in the figure title):

time.sleep
~~~~~~~~~~

As expected, time.sleep prevents any event from being processed

.. figure:: images/with_timer/time.sleep.png
   :alt: 


calling processEvents
~~~~~~~~~~~~~~~~~~~~~

40 000 events/seconds.

.. figure:: images/with_timer/processEvents.png
   :alt: 


running the eventLoop locally
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. figure:: images/with_timer/qeventloop.png
   :alt: 

That's approximately identical


our custom function
~~~~~~~~~~~~~~~~~~~

Still more or less identical (but remember that the big advantage
compared to the previous version is that in the absence of external
events, the CPU load is close to 0).

.. figure:: images/with_timer/my_sleep.png
   :alt: 


Async programming in python3(.5):
=================================

A description of async programming in python 3.5 is given in
":doc:`index`". To summarize, it is possible to use the Qt event loop as
a backend for the beautiful syntax of coroutines in python 3 using
quamash. Of course, because the quamash library is just a wrapper
translating the new python asynchronous syntax into QTimers, there is no
magic on the precision/efficiency side: for instance, the basic
coroutine ``asyncio.sleep`` gives a result similar to "Running a local
QEventLoop":

::

    async def sleep_coroutine(delay):
       await asyncio.sleep(delay)

.. figure:: images/with_timer/asyncio_no_correction.png
   :alt: 

But, obviously, we can play the same trick as before to make a precise
enough coroutine:

::

    async def sleep_coroutine(delay):
       tic = default_timer()
       if delay>0.001:
           await asyncio.sleep(delay - 0.001)
       while default_timer() < tic + delay:
           APP.processEvents()

.. figure:: images/with_timer/asyncio.png
   :alt: 

