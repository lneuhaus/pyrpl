import logging
from qtpy import QtCore, QtWidgets
import asyncio
from asyncio import TimeoutError
import quamash
import sys


logger = logging.getLogger(name=__name__)

# enable ipython QtGui support if needed
try:
    from IPython import get_ipython
    IPYTHON = get_ipython()
    IPYTHON.magic("gui qt")
except BaseException as e:
    logger.debug('Could not enable IPython gui support: %s.' % e)

APP = QtWidgets.QApplication.instance()
if APP is None:
    # logger.debug('Creating new QApplication instance "pyrpl"')
    APP = QtWidgets.QApplication(['pyrpl'])

# Main loop of the application:
# In an Ipython (Jupyter) notebook with qt integration:
#    %gui qt
#    fut = ensure_future(some_coroutine(), loop=LOOP) # executes anyway in
# the background loop
#    LOOP.run_until_complete(fut) # only returns when fut is ready
# BEWARE ! inside some_coroutine, calls to asyncio.sleep_async() have to be
# made this way:
#    asyncio.sleep(sleep_time, loop=LOOP)
# Consequently, there is a coroutine async_utils.async_sleep(time_s)
# Finally this file provide a sleep() function that waits for the execution of
# sleep_async and that should be used in place of time.sleep.
LOOP = quamash.QEventLoop()

class Event(asyncio.Event):
    """
    Events should also be running in LOOP
    """
    def __init__(self):
        super(Event, self).__init__(loop=LOOP)

async def sleep_async(time_s):
    await asyncio.sleep(time_s, loop=LOOP)

def ensure_future(coroutine):
    return asyncio.ensure_future(coroutine, loop=LOOP)


def wait(future, timeout=None):
    """
    This function is used to turn async coroutines into blocking functions:
    Returns the result of the future only once it is ready.
    ex:
    def curve(self):
        curve = scope.curve_async()
        return wait(curve)
    """
    new_future = ensure_future(asyncio.wait({future},
                                            timeout=timeout,
                                            loop=LOOP))
    if sys.version>='3.7':
        LOOP.run_until_complete(new_future)
        done, pending = new_future.result()
    else:
        loop = QtCore.QEventLoop()
        def quit(*args):
            loop.quit()
        new_future.add_done_callback(quit)
        loop.exec_()
        done, pending = new_future.result()
    if future in done:
        return future.result()
    else:
        raise TimeoutError("Timout exceeded")

def sleep(time_s):
    wait(ensure_future(sleep_async(time_s)))