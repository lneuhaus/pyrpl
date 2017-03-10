"""
This file contains a number of methods for asynchronous operations.
"""
import logging

_LOGGER = logging.getLogger(name=__name__)
try:
    from asyncio import Future, ensure_future, CancelledError, set_event_loop
except ImportError:
    _LOGGER.warning("asyncio not found, we will use concurrent.futures "
                    "instead of python 3.5 Futures.")
    from concurrent.futures import Future, CancelledError
else:
    import quamash
    loop = quamash.QEventLoop()
    set_event_loop(loop)
from PyQt4 import QtCore, QtGui

class PyrplFuture(Future):
    """
    A promise object compatible with the Qt event loop.

    We voluntarily use an object that is different from the native QFuture
    because we want a promise object that is compatible with the python 3.5+
    asyncio patterns (for instance, it implements an __await__ method...)

    public instance methods:
    ------------------------
     - result(): the method blocks until the result is ready, but it allows
     the Qt event-loop to run in parallel.

     - exception(): the method blocks until:
        a. the result is ready --> returns None
        b. an exception accured in the execution --> returns the exception
     the Qt event-loop is allowed to run in parallel.

     - done(): checks whether the result is ready or not.

     - add_done_callback(callback): add a callback to execute when result
     becomes available. Callback takes 1 argument (the result of the promise)

    - cancel(): ...

    - cancelled(): whether the promise was cancelled.

    -
    """

    def _exit_loop(self, x):
        self.loop.quit()

    def _wait_for_done(self, timeout):
        if self.cancelled():
            raise CancelledError("Future was cancelled")
        if not self.done():
            self.timer_timeout = None
            if (timeout is not None) and timeout > 0:
                self.timer_timeout = QtCore.QTimer()
                self.timer_timeout.setInterval(timeout)
                self.timer_timeout.setSingleShot(True)
                self.timer_timeout.timeout.connect(self._exit_loop)
            self.loop = QtCore.QEventLoop()
            self.add_done_callback(self._exit_loop)
            self.loop.exec_()
            if self.timer_timeout is not None:
                if not self.timer_timeout.isActive():
                    return TimeoutError("Timeout occured")


    def result(self, timeout=None):
        """
        Return the result of the call that the future represents.

        Args:
            timeout: The number of seconds to wait for the result if the future
                isn't done. If None, then there is no limit on the wait time.

        Returns:
            The result of the call that the future represents.

        Raises:
            CancelledError: If the future was cancelled.
            TimeoutError: If the future didn't finish executing before the given
                timeout.
            Exception: If the call raised then that exception will be raised.
        """

        self._wait_for_done(timeout)
        return super(PyrplFuture, self).result()

    def exception(self, timeout=None):
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
            TimeoutError: If the future didn't finish executing before the given
        """
        self._wait_for_done(timeout)
        return super(PyrplFuture, self).exception()

