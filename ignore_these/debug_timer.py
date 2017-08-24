from qtpy import QtCore, QtWidgets
import time
from pyrpl.async_utils import sleep as async_sleep

""" what is this file for? delete it? """

if False:
    from pyrpl import Pyrpl

    pyrpl = Pyrpl(config="nosetests_source.yml",
                  source="nosetests_config.yml")
    async_sleep(0.5)

    class ToPasteInNotebook(object):
        def coucou(self):
            self.count += 1
            if self.count < 1000:
                self.timer.start()

        def test_stupid_timer(self):
            self.timer = QtCore.QTimer()
            self.timer.setInterval(1) # 1 ms
            self.timer.setSingleShot(True)
            self.count = 0
            self.timer.timeout.connect(self.coucou)

            tic = time.time()
            self.timer.start()
            while self.count<10:
                async_sleep(0.01)
            duration = time.time() - tic
            assert(duration<1), duration  # should this not be >1 ???

    t = ToPasteInNotebook()
    t.test_stupid_timer()