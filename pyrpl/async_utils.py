"""
This file provides the basic functions to perform asynchronous tasks.
It provides the 3 functions:
 * ensure_future(coroutine): schedules the task described by the coroutine and
                             returns a Future that can be used as argument of
                             the following functions:
 * sleep(time_s): blocks the commandline for time_s, without blocking other
                  tasks such as gui update...
 * wait(future, timeout=None): blocks the commandline until future is set or
                               timeout expires.

BEWARE: sleep() and wait() can be used behind a qt slot (for instance in
response to a QPushButton being pressed), however, they will fail if used
inside a coroutine. In this case, one should use the builtin await (in
place of wait) and the asynchronous sleep coroutine provided below (in
place of sleep):
  * async_sleep(time_s): await this coroutine to stall the execution for a
                         time time_s within a coroutine.

These functions are provided in place of the native asyncio functions in
order to integrate properly within the IPython (Jupyter) Kernel. For this,
Main loop of the application:
In an Ipython (Jupyter) notebook with qt integration:
    %gui qt
     fut = ensure_future(some_coroutine(), loop=LOOP) # executes anyway in
the background loop
#    LOOP.run_until_complete(fut) # only returns when fut is ready
# BEWARE ! inside some_coroutine, calls to asyncio.sleep_async() have to be
# made this way:
#    asyncio.sleep(sleep_time, loop=LOOP)
# Consequently, there is a coroutine async_utils.async_sleep(time_s)
# Finally this file provides a sleep() function that waits for the execution of
# sleep_async and that should be used in place of time.sleep.

"""
import logging
from qtpy import QtWidgets
import asyncio
from asyncio import TimeoutError, futures
from asyncio.tasks import __sleep0
import qasync
import math

logger = logging.getLogger(name=__name__)

# enable ipython QtGui support if needed
try:
    from IPython import get_ipython
    IPYTHON = get_ipython()
    IPYTHON.run_line_magic("gui","qt")
except BaseException as e:
    logger.debug('Could not enable IPython gui support: %s.' % e)

APP = QtWidgets.QApplication.instance()
if APP is None:
    # logger.debug('Creating new QApplication instance "pyrpl"')
    APP = QtWidgets.QApplication(['pyrpl'])

LOOP = qasync.QEventLoop(already_running=False)  # Since tasks scheduled in this loop seem to
# fall in the standard QEventLoop, and we never explicitly ask to run this
# loop, it might seem useless to send all tasks to LOOP, however, a task
# scheduled in the default loop seem to never get executed with IPython
# kernel integration.


async def sleep_async(delay, result=None):
    """
    Replaces asyncio.sleep(time_s) inside coroutines. Deals properly with
    IPython kernel integration. The standard asyncio function get the loop
    by calling get_event_loop which doesn't return the proper loop with
    IPython.
    """

    if delay <= 0:
        await __sleep0()
        return result

    if math.isnan(delay):
        raise ValueError("Invalid delay: NaN (not a number)")

    future = LOOP.create_future()
    h = LOOP.call_later(delay,
                        futures._set_result_unless_cancelled,
                        future, result)
    try:
        return await future
    finally:
        h.cancel()


def ensure_future(coroutine):
    """
    Schedules the task described by the coroutine. Deals properly with
    IPython kernel integration.
    """
    return asyncio.ensure_future(coroutine, loop=LOOP)


def wait(future, timeout=None):
    """
    This function is used to turn async coroutines into blocking functions:
    Returns the result of the future only once it is ready. This function
    won't block the eventloop while waiting for other events.
    ex:
    def curve(self):
        curve = scope.curve_async()
        return wait(curve)

    BEWARE: never use wait in a coroutine (use builtin await instead)
    """
    # assert isinstance(future, Future) or iscoroutine(future)
    new_future = ensure_future(asyncio.wait({future},
                                            timeout=timeout))
    # if sys.version>='3.7': # this way, it was not possible to execute wait behind a qt slot !!!

    LOOP.run_until_complete(new_future)
    done, pending = new_future.result()
    # else:
    # loop = QtCore.QEventLoop()
    # def quit(*args):
    #     loop.quit()
    # new_future.add_done_callback(quit)
    # loop.exec_()
    # done, pending = new_future.result()
    if future in done:
        return future.result()
    else:
        raise TimeoutError("Timeout exceeded")


def sleep(time_s):
    """
    Blocks the commandline for time_s. This function doesn't block the
    eventloop while executing.
    BEWARE: never sleep in a coroutine (use await sleep_async(time_s) instead)
    """
    wait(ensure_future(sleep_async(time_s)))


class Event(asyncio.Event):
    """
    Use this Event instead of asyncio.Event() to signal an event. This
    version deals properly with IPython kernel integration.
    Example: Resuming scope acquisition after a pause (acquisition_module.py)
        def pause(self):
            if self._running_state=='single_async':
                self._running_state=='paused_single'
            _resume_event = Event()

        async def _single_async(self):
            for self.current_avg in range(1, self.trace_average):
                if self._running_state=='paused_single':
                    await self._resume_event.wait()
            self.data_avg = (self.data_avg * (self.current_avg-1) + \
                             await self._trace_async(0)) / self.current_avg

    """

    def __init__(self):
        super(Event, self).__init__()
