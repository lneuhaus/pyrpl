from qtpy import QtCore, QtWidgets
import time

""" what is this file for? delete it? """

APP = QtWidgets.QApplication.instance()
if APP is None:
	APP = QtWidgets.QApplication(['DEBUG_TIMER'])

from .. import Pyrpl


pyrpl = Pyrpl(config="nosetests_source.yml",
              source="nosetests_config.yml")
	
for i in range(10000):
	APP.processEvents()
	
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
        while self.count<1000:
            APP.processEvents()
        duration = time.time() - tic
        assert(duration<1), duration  # should this not be >1 ???

t = ToPasteInNotebook()
t.test_stupid_timer()