"""
The :mod:`~pyrpl.hardware_modules.iq`-module implements a variety of Digital
Signal Processing (DSP) taks that require an internal reference signal
(a so-called *local oscillator*) of arbitrary frequency. The task to perform
is selected by the values of different internal registers. The various
use-cases and necessary configuration is explained in the following sections.


Pound Drever Hall signal generation
---------------------------------------

The PDH locking technique is widely used to lock a laser beam to a
high-finesse optical cavity. The principle is to generate a strong
phase modulation of the laser beam (for instance, with an electro-optic modulator)
at a frequency exceeding the cavity bandwidth and to detect the amplitude
modulation in the beam reflected by the cavity. The amplitude
modulation is caused by the abrupt phase response of the cavity affecting
independently the sidebands from the carrier, and its sign with respect
to the imposed modulation depends on cavity detuning. The
high-speed digital signal processing of the redpitaya allows us to
perform all the modulation/demodulation steps inside the FPGA,
with modulations frequencies up to Nyquist frequecies (62.5 MHz). The
correct IQ-module settings for PDH generation are (refer to the IQ
signal schematic for explanations)::

  gain=0. # no link from demodulation to modulation stage
  amplitude=1. # amplitude of the modulation
  frequency=50e6 # Modulation frequency
  phase=0 # adjust to compensate for cable length delays
  output_direct='out1' # output to optical phase modulator
  output_signal='quadrature'
  input='in1' # input from photodiode
  bandwidth=1e5 # trade-off between noise and error-signal bandwidth
  quadrature_factor=256 # adjust for saturation level
  acbandwidth=1e4 # to prevent internal saturation problems


Network analyzer
------------------

The network analyzer uses an IQ internally to accumulate the
demodulated signal. The Network analyzer module automatically sets the
following settings for the IQ module registers::

  gain=0
  quadrature_factor=0
  output_direct=output_direct  # use output_signal to excite an internal signal
  frequency=frequency # is value is scanned over time
  bandwidth=rbw # bandwidth of the frequency analysis
  input=input
  acbandwidth=acbandwidth


Phase-frequency detector
-----------------------------
The IQ-module can be used to perform phase/frequency comparison between
the internal frequency reference and an input signal. This is done by
connecting the output multiplexer to a frequency comparator (not
represented in the schematic)::

  output_signal='pfd'


Tuneable bandpass filter
---------------------------

It is possible to realize very narrow bandpass filters by combining a
demodulation and a remodulation stage. The correct settings are::

  gain=1. # demod-> modulation gain
  amplitude=0. # no internal excitation
  frequency=1e6 # filter center frequency
  bandwidth=100 # filter bandwidth (use a tuple for high-order filters)
  quadrature_factor=0
  output_signal='ouptut_direct' # if the signal needs to be used internally
  phase=30 # eventually include some dephasing to the filter
"""
from .base_module_widget import ModuleWidget

from qtpy import QtCore, QtWidgets


class IqWidget(ModuleWidget):
    """
    Widget for the IQ module
    """

    def init_gui(self):
        super(IqWidget, self).init_gui()
        ##Then remove properties from normal property layout
        ## We will make one where buttons are stack on top of each others by functional column blocks
        for key, widget in self.attribute_widgets.items():
            layout = widget.layout_v
            self.attribute_layout.removeWidget(widget)
        self.attribute_widgets["bandwidth"].widget.set_max_cols(2)
        self.attribute_layout.addWidget(self.attribute_widgets["input"])
        self.attribute_layout.addWidget(self.attribute_widgets["acbandwidth"])
        self.button_synchronize_iqs = QtWidgets.QPushButton("Synchronize IQs")
        self.attribute_widgets["acbandwidth"].layout_v.insertWidget(3,
                                                                    self.button_synchronize_iqs)
        self.button_synchronize_iqs.clicked.connect(lambda: self.module.synchronize_iqs())

        self.attribute_layout.addWidget(self.attribute_widgets["frequency"])
        self.attribute_widgets["frequency"].layout_v.insertWidget(3,
                                                                  self.attribute_widgets["phase"])
        self.attribute_layout.addWidget(self.attribute_widgets["bandwidth"])
        self.attribute_widgets["bandwidth"].layout_v.insertWidget(3,
                                                              self.attribute_widgets["demodulation_at_2f"])
        self.attribute_layout.addWidget(self.attribute_widgets["quadrature_factor"])

        # since the singleStep is 1., the default value would be too small
        self.attribute_widgets["quadrature_factor"].widget.per_second=10
        self.attribute_layout.addWidget(self.attribute_widgets["gain"])
        self.attribute_layout.addWidget(self.attribute_widgets["amplitude"])
        self.attribute_widgets["amplitude"].layout_v.insertWidget(3,
                                                                  self.attribute_widgets["modulation_at_2f"])
        self.attribute_layout.addWidget(self.attribute_widgets["output_signal"])
        self.attribute_widgets["output_signal"].layout_v.insertWidget(3,
                                                                      self.attribute_widgets["output_direct"])
        self.attribute_layout.setStretch(0,0)
        self.attribute_layout.addStretch(1)