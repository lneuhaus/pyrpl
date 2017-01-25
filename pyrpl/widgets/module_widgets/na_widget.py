"""
A widget fot the network analyzer
"""

from .base_module_widget import ModuleWidget

from PyQt4 import QtCore, QtGui
import pyqtgraph as pg
from time import time
import numpy as np

APP = QtGui.QApplication.instance()


class NaWidget(ModuleWidget):
    """
    Network Analyzer Tab.
    """
    starting_update_rate = 0.2 # this would be a good idea to change this number dynamically when the curve becomes
    # more and more expensive to display.

    def init_gui(self):
        """
        Sets up the gui
        """
        self.main_layout = QtGui.QVBoxLayout()
        self.init_attribute_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("NA")
        self.win = pg.GraphicsWindow(title="Amplitude")
        self.win_phase = pg.GraphicsWindow(title="Phase")
        self.plot_item = self.win.addPlot(title="Magnitude (dB)")
        self.plot_item_phase = self.win_phase.addPlot(title="Phase (deg)")
        self.plot_item_phase.setXLink(self.plot_item)
        self.button_single = QtGui.QPushButton("Run single")
        self.button_single.my_label = "Single"
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_continuous.my_label = "Continuous"
        self.button_stop = QtGui.QPushButton('Stop')

        self.button_save = QtGui.QPushButton("Save curve")

        self.chunks = [] #self.plot_item.plot(pen='y')
        self.chunks_phase = []
        self.main_layout.addWidget(self.win)
        self.main_layout.addWidget(self.win_phase)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_stop)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)

        self.button_single.clicked.connect(self.run_single_clicked)
        self.button_continuous.clicked.connect(self.run_continuous_clicked)
        self.button_stop.clicked.connect(self.button_stop_clicked)
        self.button_save.clicked.connect(self.save_clicked)

        self.arrow = pg.ArrowItem()
        self.arrow.setVisible(False)
        self.arrow_phase = pg.ArrowItem()
        self.arrow_phase.setVisible(False)
        self.plot_item.addItem(self.arrow)
        self.plot_item_phase.addItem(self.arrow_phase)
        self.last_updated_point = 0
        self.last_updated_time = 0
        self.display_state(self.module.running_state)
        self.update_period = self.starting_update_rate # also modified in clear_curve.

    def autoscale(self):
        """
        log_mode = self.module.logscale
        self.plot_item.setLogMode(x=log_mod, y=None) # this seems also needed
        self.plot_item_phase.setLogMode(x=log_mod, y=None)
        """
        self.plot_item.setRange(xRange=[self.module.start_freq, self.module.stop_freq])
        self.plot_item_phase.setRange(xRange=[self.module.start_freq, self.module.stop_freq])

    def clear_curve(self):
        """
        Clear all chunks
        """
        self.update_period = self.starting_update_rate  # let's assume update of curve takes 50 ms
        while(True):
            try:
                chunk = self.chunks.pop()
                chunk_phase = self.chunks_phase.pop()
                chunk.clear()
                chunk_phase.clear()
            except IndexError:
                break

    def x_log_toggled(self):
        """
        change x_log of axis
        """
        log_mod = self.module.logscale
        self.plot_item.setLogMode(x=log_mod, y=None) # this seems also needed
        self.plot_item_phase.setLogMode(x=log_mod, y=None)
        for chunk, chunk_phase in zip(self.chunks, self.chunks_phase):
            chunk.setLogMode(xMode=log_mod, yMode=None)
            chunk_phase.setLogMode(xMode=log_mod, yMode=None)

    def scan_finished(self):
        """
        if in run continuous, needs to redisplay the number of averages
        """
        self.display_state(self.module.running_state) # display correct average number
        self.update_point(self.module.points-1, force=True) # make sure all points in the scan are updated

    def update_point(self, index, force=False):
        """
        To speed things up, the curves are plotted by chunks of 50 points. All points between last_updated_point and
        index will be redrawn.
        """
        APP.processEvents()  # Give hand back to the gui since timer intervals might be very short
        last_chunk_index = self.last_updated_point//50
        current_chunk_index = index//50

        if force or (time() - self.last_updated_time>self.update_period): # if last update time was a long time ago,
            #  update plot, otherwise we would spend more time plotting things than acquiring data...
            for chunk_index in range(last_chunk_index, current_chunk_index+1):
                self.update_chunk(chunk_index) # eventually several chunks to redraw
            self.last_updated_point = index
            self.last_updated_time = time()


            # draw arrow
            cur = self.module.current_point - 1
            visible = self.module.last_valid_point != cur + 1
            logscale = self.module.logscale
            freq = self.module.x[cur]
            xpos = np.log10(freq) if logscale else freq
            if cur > 0:
                self.arrow.setPos(xpos, abs(self.module.y_averaged[cur]))
                self.arrow.setVisible(visible)
                self.arrow_phase.setPos(xpos, 180./np.pi*np.angle(self.module.y_averaged[cur]))
                self.arrow_phase.setVisible(visible)

    def update_attribute_by_name(self, name, new_value_list):
        super(NaWidget, self).update_attribute_by_name(name, new_value_list)
        if name=="running_state":
            self.display_state(self.module.running_state)

    def update_chunk(self, chunk_index):
        """
        updates curve # chunk_index with the data from the module
        """
        while len(self.chunks) <= chunk_index: # create as many chunks as needed to reach chunk_index (in principle only
            # one curve should be missing at most)
            chunk = self.plot_item.plot(pen='y')
            chunk_phase = self.plot_item_phase.plot(pen=None, symbol='o')
            self.chunks.append(chunk)
            self.chunks_phase.append(chunk_phase)
            log_mod = self.module.logscale
            chunk.setLogMode(xMode=log_mod, yMode=None)
            chunk_phase.setLogMode(xMode=log_mod, yMode=None)

        sl = slice(max(0, 50 * chunk_index - 1), min(50 * (chunk_index + 1), self.module.last_valid_point), 1) # make sure there is an overlap between slices
        data = self.module.y_averaged[sl]
        self.chunks[chunk_index].setData(self.module.x[sl], np.abs(data))
        self.chunks_phase[chunk_index].setData(self.module.x[sl], 180./np.pi*np.angle(data))


    def run_continuous_clicked(self):
        """
        launches a continuous run
        """
        if str(self.button_continuous.text()).startswith("Pause"):
            self.module.pause()
        else:
            self.module.run_continuous()

    def run_single_clicked(self):
        """
        launches a single acquisition
        """
        if str(self.button_single.text()).startswith("Pause"):
            self.module.pause()
        else:
            self.module.run_single()

    def save_clicked(self):
        """
        Save the current curve.
        """
        self.module.save_curve()

    def display_state(self, running_state):
        """
        Displays one of the possible states
        "running_continuous", "running_single", "paused_continuous", "paused_single", "stopped"
        """
        if not running_state in ["running_continuous", "running_single", "paused_continuous", "paused_single", "stopped"]:
            raise ValueError("Na running_state should be either running_continuous, running_single, paused_continuous, "
                             "paused_single.")
        if running_state== "running_continuous":
            self.button_single.setEnabled(False)
            self.button_single.setText("Run single")
            self.button_continuous.setEnabled(True)
            self.button_continuous.setText("Pause (%i averages)"%self.module.current_averages)
            return
        if running_state== "running_single":
            self.button_single.setEnabled(True)
            self.button_single.setText("Pause")
            self.button_continuous.setEnabled(False)
            self.button_continuous.setText("Run continuous")
            return
        if running_state== "paused_single" or (running_state== "paused_continuous" and self.module.current_averages==0):
            self.button_continuous.setText("Resume continuous")
            self.button_single.setText("Resume single")
            self.button_continuous.setEnabled(True)
            self.button_single.setEnabled(True)
            return
        if running_state== "paused_continuous":
            self.button_continuous.setText("Resume continuous (%i averages)"%self.module.current_averages)
            self.button_single.setText("Run single")
            self.button_continuous.setEnabled(True)
            self.button_single.setEnabled(False)
            return
        if running_state== "stopped":
            self.button_continuous.setText("Run continuous")
            self.button_single.setText("Run single")
            self.button_continuous.setEnabled(True)
            self.button_single.setEnabled(True)
            return

    def button_stop_clicked(self):
        """
        Going to stop will impose a setup_average before next run.
        """
        self.module.stop()

    def update_plot_obsolete(self):
        """
        Update plot only every 10 ms max...

        Returns
        -------
        """
        # plot_time_start = time()
        x = self.x[:self.last_valid_point]
        y = self.data[:self.last_valid_point]

        # check if we shall display open loop tf
        if self.module.infer_open_loop_tf:
            y = y / (1.0 + y)
        mag = 20 * np.log10(np.abs(y))
        phase = np.angle(y, deg=True)
        log_mod = self.module.logscale
        self.curve.setLogMode(xMode=log_mod, yMode=None)
        self.curve_phase.setLogMode(xMode=log_mod, yMode=None)

        self.plot_item.setLogMode(x=log_mod, y=None) # this seems also needed
        self.plot_item_phase.setLogMode(x=log_mod, y=None)

        self.curve.setData(x, mag)
        self.curve_phase.setData(x, phase)

        cur = self.module.current_point - 1
        visible = self.last_valid_point!=cur + 1
        logscale = self.module.logscale
        freq = x[cur]
        xpos = np.log10(freq) if logscale else freq
        if cur>0:
            self.arrow.setPos(xpos, mag[cur])
            self.arrow.setVisible(visible)
            self.arrow_phase.setPos(xpos, phase[cur])
            self.arrow_phase.setVisible(visible)
        # plot_time = time() - plot_time_start # actually not working, because done later
        # self.update_timer.setInterval(plot_time*10*1000) # make sure plotting
        # is only marginally slowing
        # down the measurement...
        self.update_timer.setInterval(self.last_valid_point / 100)


class MyGraphicsWindow(pg.GraphicsWindow):
    def __init__(self, title, parent_widget):
        super(MyGraphicsWindow, self).__init__(title)
        self.parent_widget = parent_widget
        self.setToolTip("IIR transfer function: \n"
                        "----------------------\n"
                        "CTRL + Left click: add one more pole. \n"
                        "SHIFT + Left click: add one more zero\n"
                        "Left Click: select pole (other possibility: click on the '+j' labels below the graph)\n"
                        "Left/Right arrows: change imaginary part (frequency) of the current pole or zero\n"
                        "Up/Down arrows; change the real part (width) of the current pole or zero. \n"
                        "Poles are represented by 'X', zeros by 'O'")

    def mousePressEvent(self, *args, **kwds):
        event = args[0]
        try:
            modifier = int(event.modifiers())
            it = self.getItem(0, 0)
            pos = it.mapToScene(event.pos()) #  + it.vb.pos()
            point = it.vb.mapSceneToView(pos)
            x, y = point.x(), point.y()
            x = 10 ** x
            new_z = -100 - 1.j * x
            if modifier==QtCore.Qt.CTRL:
                self.parent_widget.module.poles += [new_z]
                self.parent_widget.attribute_widgets['poles'].set_selected(-1)
            if modifier == QtCore.Qt.SHIFT:
                self.parent_widget.module.zeros += [new_z]
                self.parent_widget.attribute_widgets['zeros'].set_selected(-1)
        except BaseException as e:
            self.parent_widget.module._logger.error(e)
        finally:
            return super(MyGraphicsWindow, self).mousePressEvent(*args, **kwds)