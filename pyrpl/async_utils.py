"""
This file contains a number of methods for asynchronous operations.
"""
import logging
from qtpy import QtCore, QtWidgets
from timeit import default_timer
import sys
logger = logging.getLogger(name=__name__)

from . import APP  # APP is only created once at the startup of PyRPL
MAIN_THREAD = APP.thread()

try:
    from asyncio import Future, ensure_future, CancelledError, \
        set_event_loop, TimeoutError
except ImportError:  # this occurs in python 2.7
    logger.debug("asyncio not found, we will use concurrent.futures "
                  "instead of python 3.5 Futures.")
    from concurrent.futures import Future, CancelledError, TimeoutError
else:
    import quamash
    set_event_loop(quamash.QEventLoop())
    LOOP = quamash.QEventLoop()


class MainThreadTimer(QtCore.QTimer):
    """
    To be able to start a timer from any (eventually non Qt) thread,
    we have to make sure that the timer is living in the main thread (in Qt,
    each thread potentially has a distinct eventloop...).

    For example, this is required to use the timer within timeit.

    we might decide one day to allow 2 event loops to run concurrently in
    separate threads, but
    1. That should be QThreads and not python threads
    2. We would have to make sure that all the gui operations are performed
    in the main thread (for instance, by moving all widgets in the
    mainthread, and probably, we would have to change some connections in
    QueuedConnections)
    ==> but this is not a supported feature for the moment and I don't see
    the advantage because the whole point of using an eventloop is to
    avoid multi-threading.

    For conveniance, MainThreadTimer is also SingleShot by default and is
    initialized with an interval as only argument.

    Benchmark:

     1. keep starting the same timer over and over --> 5 microsecond/call::

            n = [0]
            tics = [default_timer()]
            timers = [None]
            N = 100000
            timer = MainThreadTimer(0)
            timer.timeout.connect(func)
            def func():
                n[0]+=1
                if n[0] > N:
                    print('done', (default_timer() - tics[0])/N)
                    return
                timer.start()
                timers[0] = timer
                return
            func() ---> 5 microseconds per call

     2. Instantiating a new timer at each call --> 15 microsecond/call::

            n = [0]
            tics = [default_timer()]
            timers = [None]
            N = 100000
            def func():
                n[0]+=1
                if n[0] > N:
                    print('done', (default_timer() - tics[0])/N)
                    return
                timer = MainThreadTimer(0)
                timer.timeout.connect(func)
                timer.start()
                timers[0] = timer
                return
            func() ---> 15 microseconds per call

    Moreover, no catastrophe occurs when instantiating >10e6 timers
    successively

    Conclusion: it is OK to instantiate a new timer every time it is needed
    as long as a 10 microsecond overhead is not a problem.
    """

    def __init__(self, interval):
        super(MainThreadTimer, self).__init__()
        self.moveToThread(MAIN_THREAD)
        self.setSingleShot(True)
        self.setInterval(interval)




class PyrplFuture(Future):
    """
    A promise object compatible with the Qt event loop.

    We voluntarily use an object that is different from the native QFuture
    because we want a promise object that is compatible with the python 3.5+
    asyncio patterns (for instance, it implements an __await__ method...).

    Attributes:
        cancelled: Returns whether the promise has been cancelled.
        exception: Blocks until:
                a. the result is ready --> returns None
                b. an exception accured in the execution --> returns the exception the Qt event-loop is allowed to run in parallel.
        done: Checks whether the result is ready or not.
        add_done_callback (callback function): add a callback to execute when result becomes available. The callback function takes 1 argument (the result of the promise).

    Methods to implement in derived class:
        _set_data_as_result(): set
    """

    def __init__(self):
        if sys.version.startswith('3.7') or sys.version.startswith('3.6'):
            super(PyrplFuture, self).__init__(loop=LOOP) # Necessary
            # otherwise The Future will never be executed...
        else: # python 2.7, 3.5,3.6
            super(PyrplFuture, self).__init__()
        self._timer_timeout = None  # timer that will be instantiated if
        #  result(timeout) is called with a >0 value

    def result(self):
        """
        Blocks until the result is ready while running the event-loop in the background.

        Returns:
            The result of the future.
        """
        try: #  concurrent.futures.Future (python 2)
            return super(PyrplFuture, self).result(timeout=0)
        except TypeError: #  asyncio.Future (python 3)
            return super(PyrplFuture, self).result()

    def _exit_loop(self, x=None):
        """
        Parameter x=None is there such that the function can be set as
        a callback at the same time for timer_timeout.timeout (no
        argument) and for self.done (1 argument).
        """
        if not self.done():
            self.set_exception(TimeoutError("timeout occured"))
        if hasattr(self, 'loop'): # Python <=3.6
            self.loop.quit()

    def _wait_for_done(self, timeout):
        """
        Will not return until either timeout expires or future becomes "done".
        There is one potential deadlock situation here:

        The deadlock occurs if we await_result while at the same
        time, this future needs to await_result from another future
        ---> To be safe, don't use await_result() in a Qt slot...
        """
        if self.cancelled():
            raise CancelledError("Future was cancelled")  # pragma: no-cover
        if not self.done():
            self.timer_timeout = None
            if (timeout is not None) and timeout > 0:
                self._timer_timeout = MainThreadTimer(timeout*1000)
                self._timer_timeout.timeout.connect(self._exit_loop)
                self._timer_timeout.start()
            self.add_done_callback(self._exit_loop)
            #if hasattr(self, 'get_loop'): # This works unless
            # _wait_for_done is called behind a qt slot... -->NOT GOOD!!!
            #
            #    self.get_loop().run_until_complete(self)
            #else: # Python <= 3.6
            self.loop = QtCore.QEventLoop()
            self.loop.exec_()
            if self._timer_timeout is not None:
                if not self._timer_timeout.isActive():
                    return TimeoutError("Timeout occured")  # pragma: no-cover
                else:
                    self._timer_timeout.stop()

    def await_result(self, timeout=None):
        """
        Return the result of the call that the future represents.
        Will not return until either timeout expires or future becomes "done".

        There is one potential deadlock situation here:
        The deadlock occurs if we await_result while at the same
        time, this future needs to await_result from another future since
        the eventloop will be blocked.
        ---> To be safe, don't use await_result() in a Qt slot. You should
        rather use result() and add_done_callback() instead.

        Args:
            timeout: The number of seconds to wait for the result if the future
                isn't done. If None, then there is no limit on the wait time.

        Returns:
            The result of the call that the future represents.

        Raises:
            CancelledError: If the future was cancelled.
            TimeoutError: If the future didn't finish executing before the
                          given timeout.
            Exception: If the call raised then that exception will be raised.
        """

        self._wait_for_done(timeout)
        return self.result()

    def await_exception(self, timeout=None):  # pragma: no-cover
        """
        Return the exception raised by the call that the future represents.

        Args:
            timeout: The number of seconds to wait for the exception if the
                future isn't done. If None, then there is no limit on the wait
                time.

        Returns:
            The exception raised by the call that the future represents or None
            if the call completed without raising.

        Raises:
            CancelledError: If the future was cancelled.
            TimeoutError: If the future didn't finish executing before the
            given  timeout.
        """
        self._wait_for_done(timeout)
        return self.exception()

    def cancel(self):
        """
        Cancels the future.
        """
        if self._timer_timeout is not None:
            self._timer_timeout.stop()
        super(PyrplFuture, self).cancel()


def sleep(delay):
    """
    Sleeps for :code:`delay` seconds + runs the event loop in the background.

        * This function will never return until the specified delay in seconds is elapsed.
        * During the execution of this function, the qt event loop (== asyncio event-loop in pyrpl) continues to process events from the gui, or from other coroutines.
        * Contrary to time.sleep() or async.sleep(), this function will try to achieve a precision much better than 1 millisecond (of course, occasionally, the real delay can be longer than requested), but on average, the precision is in the microsecond range.
        * Finally, care has been taken to use low level system-functions to reduce CPU-load when no events need to be processed.

    More details on the implementation can be found on the page: `<https://github.com/lneuhaus/pyrpl/wiki/Benchmark-asynchronous-sleep-functions>`_.
    """
    tic = default_timer()
    end_time = tic + delay

    # 1. CPU-free sleep for delay - 1ms
    if delay > 1e-3:
        new_delay = delay - 1e-3
        loop = QtCore.QEventLoop()
        timer = MainThreadTimer(new_delay * 1000)
        timer.timeout.connect(loop.quit)
        timer.start()
        try:
            loop.exec_()
        except KeyboardInterrupt as e:  # pragma: no-cover
            # try to recover from KeyboardInterrupt by finishing the current task
            timer.setInterval(1)
            timer.start()
            loop.exec_()
            raise e
    # 2. For high-precision, manually process events 1-by-1 during the last ms
    while default_timer() < end_time:
        APP.processEvents()
