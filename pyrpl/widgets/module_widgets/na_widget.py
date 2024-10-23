"""
The network analyzer records the coherent response of the signal at the port
:code:`input` to a sinusoidal excitation of variable frequency sent to the
output selected in :code:`output_direct`.

.. note:: If :code:`output_direct='off'`, another module's input can be set
          to :code:`networkanalyzer` to test its response to a frequency sweep.

* :attr:`~pyrpl.software_modules.network_analyzer.NetworkAnalyzer.amplitude`
  sets the amplitude of the sinusoidal excitation in Volts.
* :attr:`~pyrpl.software_modules.network_analyzer.NetworkAnalyzer.start_freq`/:attr:`~pyrpl.software_modules.network_analyzer.NetworkAnalyzer.stop_freq`
  define the frequency range over which a transfer function is recorded.
  Swapping the values of :code:`start_freq` and :code:`stop_freq` reverses the
  direction of the frequency sweep. Setting :code:`stop_freq = start_freq`
  enables the "zero-span" mode, where the coherent response at a constant
  frequency is recorded as a function of time.
* :attr:`~pyrpl.software_modules.network_analyzer.NetworkAnalyzer.points`
  defines the number of frequency points in the recorded transfer function.
* :attr:`~pyrpl.software_modules.network_analyzer.NetworkAnalyzer.rbw` is
  the cutoff frequency of the low-pass filter after demodulation. Furthermore,
  the time :math:`\\tau` spent to record each point is
  :math:`\\tau=\\texttt{average_per_point} / \\texttt{rbw}`.
* :attr:`~pyrpl.software_modules.network_analyzer.NetworkAnalyzer.average_per_point`:
  Each point is averaged inside the FPGA before being retrieved by the
  client computer that runs PyRPL. You should increase this parameter or
  decrease :code:`rbw` if the communication time between the Red Pitaya and
  the client computer limits the acquisition speed.
* :attr:`~pyrpl.software_modules.network_analyzer.NetworkAnalyzer.acbandwidth`
  is the cutoff frequency of a high-pass filter applied to the input before
  demodulation. A setting of zero disables the high-pass filter.
* :attr:`~pyrpl.software_modules.network_analyzer.NetworkAnalyzer.logscale`
  enables the use of a logarithmic scale for the frequency axis, resulting in
  a logarithmic distribution of the frequency points as well.
* :attr:`~pyrpl.software_modules.network_analyzer.NetworkAnalyzer.infer_open_loop_tf`
  applies the transformation :math:`T \\rightarrow \\frac{T}{1+T}` to the displayed
  transfer function to correct for the effect of a closed feedback loop
  (not implemented at the moment).
"""

from .base_module_widget import ModuleWidget
from.acquisition_module_widget import AcquisitionModuleWidget

from qtpy import QtCore, QtWidgets
import pyqtgraph as pg
from time import time
import numpy as np
import sys


class NaWidget(AcquisitionModuleWidget):
    """
    Network Analyzer Tab.
    """
    starting_update_rate =  0.2 # this would be a good idea to change this number dynamically when the curve becomes
    CHUNK_SIZE = 500
    # more and more expensive to display.

    def init_gui(self):
        """
        Sets up the gui
        """
        #self.main_layout = QtWidgets.QVBoxLayout()
        self.init_main_layout(orientation="vertical")
        self.init_attribute_layout()
        self.button_layout = QtWidgets.QHBoxLayout()
        #self.setLayout(self.main_layout)
        self.setWindowTitle("NA")
        self.win = pg.GraphicsLayoutWidget(title="Magnitude")

        self.label_benchmark = pg.LabelItem(justify='right')
        self.win.addItem(self.label_benchmark, row=1,col=0)
        self._last_benchmark_value = np.nan

        self.win_phase = pg.GraphicsLayoutWidget(title="Phase")
        self.plot_item = self.win.addPlot(row=1, col=0, title="Magnitude (dB)")
        self.plot_item_phase = self.win_phase.addPlot(row=1, col=0,
                                                      title="Phase (deg)")
        self.plot_item_phase.setXLink(self.plot_item)
        self.button_single = QtWidgets.QPushButton("Run single")
        self.button_single.my_label = "Single"
        self.button_continuous = QtWidgets.QPushButton("Run continuous")
        self.button_continuous.my_label = "Continuous"
        self.button_stop = QtWidgets.QPushButton('Stop')

        self.button_save = QtWidgets.QPushButton("Save curve")

        self.chunks = [] #self.plot_item.plot(pen='y')
        self.chunks_phase = []
        self.main_layout.addWidget(self.win)
        self.main_layout.addWidget(self.win_phase)

        aws = self.attribute_widgets
        self.attribute_layout.removeWidget(aws["trace_average"])
        self.attribute_layout.removeWidget(aws["curve_name"])

        ######################
        self.groups = {}
        self.layout_groups = {}
        for label, wids in [('Channels', ['input', 'output_direct']),
                            ('Frequency', ['start_freq', 'stop_freq',
                                           'points', 'logscale']),
                            ('Setup', ['amplitude', 'acbandwidth']),
                            ('Averaging', ['average_per_point', 'rbw']),
                            ('Auto-bandwidth', ['auto_bandwidth', 'q_factor_min']),
                            ('Auto-amplitude', ['auto_amplitude', 'target_dbv',
                                                'auto_amp_min', 'auto_amp_max'])]:
            self.groups[label] = QtWidgets.QGroupBox(label)
            self.layout_groups[label] = QtWidgets.QGridLayout()
            self.groups[label].setLayout(self.layout_groups[label])
            self.attribute_layout.addWidget(self.groups[label])
            for index, wid in enumerate(wids):
                self.attribute_layout.removeWidget(aws[wid])
                self.layout_groups[label].addWidget(aws[wid], int(index%2 + 1), int(index/2 + 1))
        #########################


        #self.button_layout.addWidget(aws["trace_average"])
        #self.button_layout.addWidget(aws["curve_name"])

        super(NaWidget, self).init_gui()
        #self.button_layout.addWidget(self.button_single)
        #self.button_layout.addWidget(self.button_continuous)
        #self.button_layout.addWidget(self.button_stop)
        #self.button_layout.addWidget(self.button_save)
        #self.main_layout.addLayout(self.button_layout)

        #self.button_single.clicked.connect(self.run_single_clicked)
        #self.button_continuous.clicked.connect(self.run_continuous_clicked)
        #self.button_stop.clicked.connect(self.button_stop_clicked)
        #self.button_save.clicked.connect(self.save_clicked)




        self.arrow = pg.ArrowItem()
        self.arrow.setVisible(False)
        self.arrow_phase = pg.ArrowItem()
        self.arrow_phase.setVisible(False)
        self.plot_item.addItem(self.arrow)
        self.plot_item_phase.addItem(self.arrow_phase)
        self.last_updated_point = 0
        self.last_updated_time = 0
        #self.display_state(self.module.running_state)
        self.update_running_buttons()
        self.update_period = self.starting_update_rate # also modified in clear_curve.

        # Not sure why the stretch factors in button_layout are not good by
        # default...
        #self.button_layout.setStretchFactor(self.button_single, 1)
        #self.button_layout.setStretchFactor(self.button_continuous, 1)
        #self.button_layout.setStretchFactor(self.button_stop, 1)
        #self.button_layout.setStretchFactor(self.button_save, 1)
        self.x_log_toggled() # Set the axis in logscale if it has to be

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
        self.label_benchmark.setText("")

    def x_log_toggled(self):
        """
        change x_log of axis
        """
        log_mod = self.module.logscale
        self.plot_item.setLogMode(x=log_mod, y=None) # this seems also needed
        self.plot_item_phase.setLogMode(x=log_mod, y=None)
        for chunk, chunk_phase in zip(self.chunks, self.chunks_phase):
            chunk.setLogMode(log_mod, None)
            chunk_phase.setLogMode(log_mod, None)

    def scan_finished(self):
        """
        if in run continuous, needs to redisplay the number of averages
        """
        self.update_current_average()
        self.update_point(self.module.points-1, force=True) # make sure all points in the scan are updated

    def set_benchmark_text(self, text):
        self.label_benchmark.setText(text)

    def update_point(self, index, force=False):
        """
        To speed things up, the curves are plotted by chunks of
        self.CHUNK_SIZE points. All points between last_updated_point and
        index will be redrawn.
        """
        # APP.processEvents()  # Give hand back to the gui since timer intervals might be very short
        last_chunk_index = self.last_updated_point//self.CHUNK_SIZE
        current_chunk_index = index//self.CHUNK_SIZE

        rate = self.module.measured_time_per_point
        if not np.isnan(rate) and self._last_benchmark_value != rate:
            theory = self.module.time_per_point
            self.set_benchmark_text("ms/pt: %.1f (theory: %.1f)"%(
                                                             rate*1000,
                                                             theory*1000))

        if force or (time() - self.last_updated_time > self.update_period):
            #  if last update time was a long time ago,
            #  update plot, otherwise we would spend more time plotting things than acquiring data...
            for chunk_index in range(last_chunk_index, current_chunk_index+1):
                self.update_chunk(chunk_index) # eventually several chunks to redraw
            self.last_updated_point = index
            self.last_updated_time = time()

            # draw arrow
            cur = self.module.current_point - 1
            visible = self.module.last_valid_point != cur + 1
            logscale = self.module.logscale
            freq = self.module.data_x[cur]
            xpos = np.log10(freq) if logscale else freq
            if cur > 0:
                self.arrow.setPos(xpos,
                                  self._magnitude(self.module.data_avg[
                                                      cur]))
                self.arrow.setVisible(visible)
                self.arrow_phase.setPos(xpos,
                                        self._phase(
                                            self.module.data_avg[cur]))
                self.arrow_phase.setVisible(visible)

    def _magnitude(self, data):
        return 20. * np.log10(np.abs(data)+sys.float_info.epsilon)

    def _phase(self, data):
        return np.angle(data, deg=True)

    def update_attribute_by_name(self, name, new_value_list):
        super(NaWidget, self).update_attribute_by_name(name, new_value_list)
        if name == "_running_state":
            #self.display_state(self.module.running_state)
            self.update_running_buttons()

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
            chunk.setLogMode(log_mod, None)
            chunk_phase.setLogMode(log_mod, None)

        sl = slice(max(0, self.CHUNK_SIZE * chunk_index - 1),
                   min(self.CHUNK_SIZE * (chunk_index + 1),
                       self.module.last_valid_point),
                       1) # make sure there is an overlap between slices
        data = self.module.data_avg[sl]
        x = np.real(self.module.data_x[sl])
        self.chunks[chunk_index].setData(x, self._magnitude(data))
        self.chunks_phase[chunk_index].setData(x, self._phase(data))

    #def run_continuous_clicked(self):
    #    """
    #    launches a continuous run
    #    """
    #    if str(self.button_continuous.text()).startswith("Pause"):
    #        self.module.pause()
    #    else:
    #        self.module.continuous()

    #def run_single_clicked(self):
    #    """
    #    launches a single acquisition
    #    """
    #    if str(self.button_single.text()).startswith("Pause"):
    #        self.module.pause()
    #    else:
    #        self.module.single_async()

    #def save_clicked(self):
    #    """
    #    Save the current curve.
    #    """
    #    self.module.save_curve()

    def display_state(self, running_state):
        """
        Displays one of the possible states
        "running_continuous", "running_single", "paused_continuous", "paused_single", "stopped"
        """
        if not running_state in ["running_continuous",
                                 "running_single",
                                 "paused",
                                 "stopped"]:
            raise ValueError("Na running_state should be either "
                             "running_continuous, "
                             "running_single, "
                             "paused or "
                             "stopped")
        if running_state=="running_continuous":
            self.button_single.setEnabled(False)
            self.button_single.setText("Run single")
            self.button_continuous.setEnabled(True)
            self.button_continuous.setText("Pause")
            return
        if running_state== "running_single":
            self.button_single.setEnabled(True)
            self.button_single.setText("Pause")
            self.button_continuous.setEnabled(False)
            self.button_continuous.setText("Run continuous")
            return
        if running_state == "paused":
            self.button_continuous.setText("Resume continuous")
            self.button_single.setText("Run single")
            self.button_continuous.setEnabled(True)
            self.button_single.setEnabled(False)
            return
        if running_state == "stopped":
            self.button_continuous.setText("Run continuous")
            self.button_single.setText("Run single")
            self.button_continuous.setEnabled(True)
            self.button_single.setEnabled(True)
            return

    #def button_stop_clicked(self):
    #    """
    #    Going to stop will impose a setup_average before next run.
    #    """
    #    self.module.stop()


class MyGraphicsWindow(pg.GraphicsLayoutWidget):
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
            return super(GraphicsLayoutWidget, self).mousePressEvent(*args, **kwds)