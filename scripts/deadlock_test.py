from PyQt4 import QtCore, QtGui
from asyncio import Future, set_event_loop
from quamash import QEventLoop

LOOP = QEventLoop()
set_event_loop(LOOP)


class CurveFuture(Future):
    def __init__(self):
        super(CurveFuture, self).__init__()
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.set_res)
        self.timer.start()
        self.loop = QtCore.QEventLoop()

    def set_res(self):
        self.set_result([1, 2, 3])

    def await_result(self):
        self.add_done_callback(self.quit_loop)
        self.loop.exec_()
        return self.result()

    def quit_loop(self, val):
        self.loop.quit()


class RunFuture(Future):
    def __init__(self):
        super(RunFuture, self).__init__()
        self.loop = QtCore.QEventLoop()
        self.dummy_timer = QtCore.QTimer()
        self.dummy_timer.setSingleShot(True)
        self.dummy_timer.setInterval(0)
        self.dummy_timer.timeout.connect(self.set_res)
        self.dummy_timer.start()

    def set_res(self):
        res = 0
        for i in range(3):
            curve = CurveFuture()
            res += mean(curve.await_result())
        self.set_result(res)

    def await_result(self):
        self.add_done_callback(self.quit_loop)
        self.loop.exec_()
        return self.result()

    def quit_loop(self, val):
        self.loop.quit()


class AcqFuture(Future):
    def __init__(self):
        super(AcqFuture, self).__init__()
        self.loop = QtCore.QEventLoop()
        self.dummy_timer = QtCore.QTimer()
        self.dummy_timer.setSingleShot(True)
        self.dummy_timer.setInterval(0)
        self.dummy_timer.timeout.connect(self.set_res)
        self.dummy_timer.start()

    def set_res(self):
        res = 0
        for i in range(3):
            run = RunFuture()
            res += mean(run.await_result())
        self.set_result(res)

    def await_result(self):
        self.add_done_callback(self.quit_loop)
        self.loop.exec_()
        return self.result()

    def quit_loop(self, val):
        self.loop.quit()


## La chose suivante fonctionne
curve = CurveFuture()
curve.await_result()


## La chose suivante fonctionne
run = RunFuture()
run.await_result()

## La chose suivante bloque
acq = AcqFuture()
acq.await_result()