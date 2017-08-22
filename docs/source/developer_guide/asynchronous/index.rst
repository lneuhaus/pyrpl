Requirements for an asynchronous interface compatible with python 3 asyncio
*******************************************************************************


asynchronous programming in python 3
====================================

The idea behind async programming in python 3 is to avoid callbacks
because they make the code difficult to read. Instead, they are replaced
by "coroutines": a coroutine is a function that is declared with the
``async def`` keyword. Its execution can be stopped and restarted upon
request at each ``await`` statement. This allows not to break loops into
several chained timer/signal/slot mechanisms and makes the code much
more readable (actually, very close to the corresponding synchronous
function). Let's see that on an example:

::

    %pylab qt # in a notebook, we need the qt event loop to run in the background
    import asyncio
    import scipy.fftpack
    import quamash # quamash allows to use the asyncio syntax of python 3 with the Qt event loop. Not sure how mainstream the library is...
    from PyQt4 import QtCore, QtGui
    import asyncio
    loop = quamash.QEventLoop()
    asyncio.set_event_loop(loop) # set the qt event loop as the loop to be used by asyncio


    class Scope(object):
        async def run_single(self, avg):
            y_avg = zeros(100)
            for i in range(avg):
                await asyncio.sleep(1)
                y_avg+=rand(100)
            return y_avg

    class SpecAn(object):
        scope = Scope()

        async def run_single(self, avg):
            y = zeros(100, dtype=complex)
            for i in range(avg):
                trace = await self.scope.run_single(1)
                y+= scipy.fftpack.fft(trace)
            return y

    sa = SpecAn()

    v = asyncio.ensure_future(sa.run_single(10)) # to send a coroutine to the asyncio event loop, use ensure_future, and get a future...

    v.result() # raise InvalidStateError until result is ready, then returns the averaged curve

Wonderful !! As a comparison, the same code written with QTimers (in
practice, the code execution is probably extremely similar)

::

    %pylab qt
    import asyncio
    import scipy.fftpack
    import quamash
    from PyQt4 import QtCore, QtGui
    APP = QtGui.QApplication.instance()
    import asyncio
    from promise import Promise
    loop = quamash.QEventLoop()
    asyncio.set_event_loop(loop)


    class MyPromise(Promise):
        def get(self):
            while self.is_pending:
                APP.processEvents()
            return super(MyPromise, self).get()


    class Scope(object):
        def __init__(self):
            self.timer = QtCore.QTimer()
            self.timer.setSingleShot(True)
            self.timer.setInterval(1000)
            self.timer.timeout.connect(self.check_for_curve)

        def run_single(self, avg):
            self.current_avg = 0
            self.avg = avg
            self.y_avg = zeros(100)
            self.p = MyPromise()
            self.timer.start()
            return self.p

        def check_for_curve(self):
            if self.current_avg<self.avg:
                self.y_avg += rand(100)
                self.current_avg += 1
                self.timer.start()
            else:
                self.p.fulfill(self.y_avg)


    class SpecAn(object):
        scope = Scope()

        def __init__(self):
            timer = QtCore.QTimer()
            timer.setSingleShot(True)
            timer.setInterval(1000)

        def run_single(self, avg):
            self.avg = avg
            self.current_avg = 0
            self.y_avg = zeros(100, dtype=complex)
            p = self.scope.run_single(1)
            p.then(self.average_one_curve)
            self.p = MyPromise()
            return self.p

        def average_one_curve(self, trace):
            print('av')
            self.current_avg+=1
            self.y_avg+=scipy.fftpack.fft(trace)
            if self.current_avg>=self.avg:
                self.p.fulfill(self.y_avg)
            else:
                p = self.scope.run_single(1)
                p.then(self.average_one_curve)

    sa = SpecAn()

... I dont blame you if you do not want to read the example above
because its so lengthy! The loop variables have to be passed across
functions via instance attributes, there's no way of clearly visualizing
the execution flow. This is terrible to read and this pretty much what
we have to live with in the asynchronous part of pyrpl if we want pyrpl
to be compatible with python 2 (this is now more or less confined in
AcquisitionManager now).

Can we make that compatible with python 2
=========================================

The feature presented here is only compatible with python 3.5+ (by
changing slightly the syntax, we could make it work on python 3.4). On
the other hand, for python 2: the only backport is the library trollius,
but it is not under development anymore, also, I am not sure if the
syntax is exactly identical).

In other words, if we want to stay python 2 compatible, we cannot use
the syntactic sugar of coroutines in the pyrpl code, we have to stick to
the spaghetti-like callback mess. However, I would like to make the
asynchronous parts of pyrpl fully compatible (from the user point of
view) with the asyncio mechanism. This way, users of python 3 will be
able to use functions such as run\_single as coroutines and write
beautiful code with it (eventhough the inside of the function looks like
spaghetti code due to the constraint of being python 2 compatible).

To make specifications a bit clearer, let's see an example of what a
python 3 user should be allowed to do:

::

    async def my_coroutine(n):
        c1 = zeros(100)
        c2 = zeros(100)

        for i in range(n):
            print("launching f")
            f = asyncio.ensure_future(scope.run_single(1))
            print("launching g")
            g = asyncio.ensure_future(na.run_single(1))
            print("=======")
            c1+= await f
            c2+= await g
            print("f returned")
            print("g returned")

        return c1 + c2

    p = asyncio.ensure_future(my_coroutine(3))

In this example, the user wants to ask *simultaneously* the na and the
scope for a single curve, and when both curves are ready, do something
with them and move to the next iteration. The following python 3 classes
would easily do the trick:

::

    %pylab qt
    import asyncio
    import scipy.fftpack
    import quamash
    from PyQt4 import QtCore, QtGui
    import asyncio
    loop = quamash.QEventLoop()
    asyncio.set_event_loop(loop)


    class Scope(object):
        async def run_single(self, avg):
            y_avg = zeros(100)
            for i in range(avg):
                await asyncio.sleep(1)
                y_avg+=rand(100)
            return y_avg


    class Na(object):
        async def run_single(self, avg):
            y_avg = zeros(100)
            for i in range(avg):
                await asyncio.sleep(1)
                y_avg+=rand(100)
            return y_avg

    scope = Scope()
    na = Na()

What I would like is to find a way to make the same happen without
writing any line of code in pyrpl that is not valid python 2.7...
Actually, it seems the following code does the trick:

::

    try:
        from asyncio import Future, ensure_future
    except ImportError:
        from concurrent.futures import Future

    class MyFuture(Future):
        def __init__(self):
            super(MyFuture, self).__init__()
            self.timer = QtCore.QTimer()
            self.timer.timeout.connect(lambda : self.set_result(rand(100)))
            self.timer.setSingleShot(True)
            self.timer.setInterval(1000)
            self.timer.start()

        def _exit_loop(self, x):
            self.loop.quit()

        def result(self):
            if not self.done():
                self.loop = QtCore.QEventLoop()
                self.add_done_callback(self._exit_loop)
                self.loop.exec_()
            return super(MyFuture, self).result()

    class AsyncScope(object):
        def run_single(self, avg):
            self.f = MyFuture()
            return self.f

    a = AsyncScope()


Asynchronous sleep function benchmarks
=========================================

This is contained in :doc:`benchmark`.

