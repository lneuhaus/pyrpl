"""
The :class:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer`
allows to measure the spectrum (= the squared modulus of the
Fourier-transformed autocorrelation function) of internal and external
signals in PyRPL.

The SpectrumAnalyzer has 2 different working modes:

* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.baseband` :code:`= True`
  *(baseband mode)*: The Fourier transform is directly applied on the sampled
  data. The frequency range of spectra always starts at zero by design in
  baseband mode. Two inputs can be used in this mode to compute spectra of
  two different signals. Furthermore, the complex cross-spectrum (containing
  magnitude and phase information) between the two inputs can be computed.
* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.baseband` :code:`= False`
  (*iq-mode - not available in the current version*):
  The input signals are first frequency-shifted by an
  :mod:`~pyrpl.hardware_modules.iq`-module and only then Fourier-transformed.
  This mode allows to study a narrow frequency span around an arbitrary center
  frequency.

The following attributes can be manipulated by the SpectrumAnalyzer widget:

* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.span`:
  The span of frequencies over which a spectrum is acquired.
  In baseband mode, the actual span is half of this value
  (because no additional information is given in half-spectrum with negative
  frequencies).
* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.rbw`:
  Resolution bandwidth of the spectrum to acquire (:code:`span` and
  :code:`bandwidth` are linked and cannot be set independently).
* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.display_unit`:
  The unit in which the spectrum is plotted on the screen. Internally, e.g.
  in saved measurements, all spectra are represented in units of
  :math:`\\mathrm{V}_\\mathrm{pk}^2`.
* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.window`:
  The type of window used for the Fourier transform. See
  scipy.signal.get_window for a list of available options.
* :attr:`~pyrpl.software_modules.spectrum_analyzer.SpectrumAnalyzer.acbandwidth`
  *(only available with* :code:`baseband=False` *)*: The cut-off frequency of
  the high-pass filter before frequency-shifting (=demodulation) of the input
  signal.
"""

import logging
logger = logging.getLogger(name=__name__)
from qtpy import QtCore, QtWidgets
import pyqtgraph as pg
from time import time
import numpy as np
from .base_module_widget import ModuleWidget
from ..attribute_widgets import DataWidget
from ...errors import NotReadyError
from .acquisition_module_widget import AcquisitionModuleWidget


class BasebandAttributesWidget(QtWidgets.QWidget):
    def __init__(self, specan_widget):
        super(BasebandAttributesWidget, self).__init__()
        self.h_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.h_layout)
        aws = specan_widget.attribute_widgets

        self.v_layout1 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout1)
        for name in ["display_input1_baseband", "display_input2_baseband"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout1.addWidget(widget)

        self.v_layout2 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout2)
        for name in ["input1_baseband", "input2_baseband"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout2.addWidget(widget)

        self.v_layout3 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout3)
        for name in ["display_cross_amplitude"]:#, "display_cross_phase"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout3.addWidget(widget)


class IqModeAttributesWidget(QtWidgets.QWidget):
    def __init__(self, specan_widget):
        super(IqModeAttributesWidget, self).__init__()
        self.h_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.h_layout)
        aws = specan_widget.attribute_widgets

        self.v_layout1 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout1)
        for name in ["center", "input"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout1.addWidget(widget)


class OtherAttributesWidget(QtWidgets.QWidget):
    def __init__(self, specan_widget):
        super(OtherAttributesWidget, self).__init__()
        self.h_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.h_layout)
        aws = specan_widget.attribute_widgets

        self.v_layout1 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout1)
        for name in ["baseband", "acbandwidth"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout1.addWidget(widget)

        self.v_layout2 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout2)
        for name in ["span", "window"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout2.addWidget(widget)

        self.v_layout3 = QtWidgets.QVBoxLayout()
        self.h_layout.addLayout(self.v_layout3)
        for name in ["rbw", "display_unit"]:
            widget = aws[name]
            specan_widget.attribute_layout.removeWidget(widget)
            self.v_layout3.addWidget(widget)


class SpecAnWidget(AcquisitionModuleWidget):
    _display_max_frequency = 25  # max 25 Hz framerate
    def init_gui(self):
        """
        Sets up the gui.
        """
        self.ch_col = ('magenta', 'blue', 'green')
        self.last_data = None
        self.init_main_layout(orientation="vertical")
        #self.main_layout = QtWidgets.QVBoxLayout()
        self.module.__dict__['curve_name'] = 'pyrpl spectrum'
        self.init_attribute_layout()

        self.other_widget = OtherAttributesWidget(self)
        self.attribute_layout.addWidget(self.other_widget)

        self.iqmode_widget = IqModeAttributesWidget(self)
        self.attribute_layout.addWidget(self.iqmode_widget)

        self.baseband_widget = BasebandAttributesWidget(self)
        self.attribute_layout.addWidget(self.baseband_widget)


        self.button_layout = QtWidgets.QHBoxLayout()
        #self.setLayout(self.main_layout)
        # self.setWindowTitle("Spec. An.")
        #self.win = pg.GraphicsLayoutWidget(title="PSD")
        #self.main_layout.addWidget(self.win)

        self.win2 = DataWidget(title='Spectrum')
        self.main_layout.addWidget(self.win2)

        #self.plot_item = self.win.addPlot(title="PSD")
        #self.curve = self.plot_item.plot(pen=self.ch_col[0][0])

        #self.curve2 = self.plot_item.plot(pen=self.ch_col[1][0]) # input2
        # spectrum in
        # baseband
        #self.curve_cross = self.plot_item.plot(pen=self.ch_col[2][0]) #
        # curve for


        super(SpecAnWidget, self).init_gui()

        aws = self.attribute_widgets


        aws['display_input1_baseband'].setStyleSheet("color: %s" %
                                                   self.ch_col[0])
        aws['display_input2_baseband'].setStyleSheet("color: %s" %
                                                   self.ch_col[1])
        aws['display_cross_amplitude'].setStyleSheet("color: %s" %
                                                   self.ch_col[2])
        # Not sure why the stretch factors in button_layout are not good by
        # default...

        self.attribute_layout.addStretch(1)
        self.update_baseband_visibility()

    def update_attribute_by_name(self, name, new_value_list):
        super(SpecAnWidget, self).update_attribute_by_name(name, new_value_list)
        if name in ['_running_state']:
            self.update_running_buttons()
        if name in ['baseband']:
            self.update_baseband_visibility()

    def update_baseband_visibility(self):
        self.baseband_widget.setEnabled(self.module.baseband)
        self.iqmode_widget.setEnabled(not self.module.baseband)


    #### def update_rbw_visibility(self):
    ####     self.attribute_widgets["rbw"].widget.setEnabled(not
    #### self.module.rbw_auto)

    def autoscale_x(self):
        """Autoscale pyqtgraph"""
        mini = self.module.frequencies[0]
        maxi = self.module.frequencies[-1]
        self.win2.setRange(xRange=[mini,
                                   maxi])
        # self.plot_item.autoRange()

    def unit_changed(self):
        self.display_curve(self.last_data)
        self.win2.autoRange()

    # def run_continuous_clicked(self):
    #     """
    #     Toggles the button run_continuous to stop or vice versa and starts the acquisition timer
    #     """
    #
    #     if str(self.button_continuous.text()).startswith("Run continuous"):
    #         self.module.continuous()
    #     else:
    #         self.module.pause()

    # def run_single_clicked(self):
    #     if str(self.button_single.text()).startswith('Stop'):
    #         self.module.stop()
    #     else:
    #         self.module.single_async()

    def display_curve(self, datas):
        if datas is None:
            return
        x, y = datas

        arr = np.array((datas[0], datas[1][1]))
        self.win2._set_widget_value(datas)

        self.last_data = datas
        freqs = datas[0]
        to_units = lambda x:self.module.data_to_display_unit(x,
                                                  self.module.attributes_last_run["rbw"])
        if not self.module.baseband: # iq mode, only 1 curve to display
            self.win2._set_widget_value((freqs, datas[1]), transform_magnitude=to_units)
        else: # baseband mode: data is (spec1, spec2, real(cross), imag(cross))
            spec1, spec2, cross_r, cross_i = datas[1]
            data = []
            if self.module.display_input1_baseband:
                data.append(spec1) #np.array([np.nan]*len(x))
            if self.module.display_input2_baseband:
                data.append(spec2) # = np.zeros(len(x))# np.array([np.nan]*len(x))
            if self.module.display_cross_amplitude:
                data.append(cross_r + 1j*cross_i) # = np.zeros(len(x)) # np.array([np.nan]*len(x))
            self.win2._set_widget_value((freqs, data),
                                        transform_magnitude=to_units)
        self.update_current_average()

    def display_curve_old(self, datas):
        """
        Displays all active channels on the graph.
        """
        self.last_data = datas
        freqs = datas[0]
        to_units = lambda x:self.module.data_to_display_unit(x,
                                                  self.module.attributes_last_run["rbw"])
        if not self.module.baseband: # baseband mode, only 1 curve to display
            self.curve.setData(freqs, to_units(datas[1]))
            self.curve.setVisible(True)
            self.curve2.setVisible(False)
            self.curve_cross.setVisible(False)
        else: # baseband mode: data is (spec1, spec2, real(cross), imag(cross))
            spec1, spec2, cross_r, cross_i = datas[1]
            self.curve.setData(freqs, to_units(spec1))
            self.curve.setVisible(self.module.display_input1_baseband)

            self.curve2.setData(freqs, to_units(spec2))
            self.curve2.setVisible(self.module.display_input2_baseband)

            cross = cross_r + 1j*cross_i
            cross_mod = abs(cross)
            self.curve_cross.setData(freqs, to_units(cross_mod))
            self.curve_cross.setVisible(self.module.display_cross_amplitude)

            # phase still needs to be implemented
        self.update_running_buttons()
