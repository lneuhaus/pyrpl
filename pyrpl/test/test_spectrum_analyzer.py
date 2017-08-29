import logging
logger = logging.getLogger(name=__name__)
import numpy as np
from time import sleep
from qtpy import QtCore, QtWidgets
from pyrpl.test.test_base import TestPyrpl
from pyrpl import APP


class TestClass(TestPyrpl):

    def teardown(self):
        """ make 100% sure that specan has stopped """
        self.pyrpl.spectrumanalyzer.stop()

    def test_specan_stopped_at_startup(self):
        """
        This was so hard to detect, I am making a unit test
        """
        # this test is not efficient as nothing guarantees that it will be the first test that is executed
        assert(self.pyrpl.spectrumanalyzer.running_state=='stopped')

    def test_no_write_in_config(self):
        """
        Make sure the spec an isn't continuously writing to config file,
        even in running mode.
        :return:
        """
        self.pyrpl.spectrumanalyzer.setup_attributes = dict(span=1e5,
                                            input="out1",
                                            running_state='running_continuous')
        old = self.pyrpl.c._save_counter
        for i in range(10):
            sleep(0.01)
            APP.processEvents()
        new = self.pyrpl.c._save_counter
        self.pyrpl.spectrumanalyzer.stop()
        assert (old == new), (old, new)

    def test_flatness_baseband(self):
        for span in [5e4, 1e5, 5e5, 1e6, 2e6]:
            sa = self.pyrpl.spectrumanalyzer
            sa.setup(baseband=True,
                      center=0,
                      window='flattop',
                      span=span,
                      input1_baseband="asg0",
                      running_state='stopped')
            asg = self.pyrpl.rp.asg0
            asg.setup(frequency=1e5,
                      amplitude=1.0,
                      trigger_source='immediately',
                      offset=0,
                      waveform='sin')
            freqs = np.linspace(sa.rbw*3, sa.span/2-sa.rbw*3, 11)
            points = []
            for freq in freqs:
                sa._logger.info("Testing flatness for span %f and frequency "
                                "freq %f...", span, freq)
                asg.frequency = freq
                curve = self.pyrpl.spectrumanalyzer.curve()[0]
                assert(abs(sa.frequencies[np.argmax(curve)] - freq) < sa.rbw), \
                    (sa.frequencies[np.argmax(curve)], freq, sa.rbw)
                points.append(max(curve))
                assert abs(max(curve) - asg.amplitude**2) < 0.01, max(curve)
                assert abs(max(sa.data_to_unit(curve,
                                               "Vrms^2/Hz",
                                                sa.rbw)*sa.rbw) -
                           (asg.amplitude**2)/2)<0.01, max(curve)

    def test_white_noise(self):
        """
        Make sure a white noise results in a flat spectrum, with a PSD equal to
        <V^2> when integrated from 0 Hz to Nyquist frequency.
        """
        self.asg = self.pyrpl.rp.asg0
        for amplitude in np.linspace(0.05, 0.4, 4):
            self.asg.setup(amplitude=0.4,
                           waveform='noise',
                           trigger_source='immediately')

            self.sa = self.pyrpl.spectrumanalyzer
            self.sa.setup(input1_baseband=self.asg,
                          span=125e6,
                          trace_average=10)
            in1, in2, cre, cim = self.sa.single()
            df = self.sa.frequencies[1] - self.sa.frequencies[0]

            # average neighbouring points
            in1_av = in1[:-(len(in1)%1000)].reshape(len(in1)//1000, 1000).mean(
                axis=1)

            if False: # Remove this to check flatness...
                # Make sure curve is flat
                assert(np.max(in1_av)-np.min(in1_av))/np.mean(in1_av) < 0.1

            integral = sum(self.sa.data_to_unit(in1, 'Vrms^2/Hz', self.sa.rbw))*df/ np.sqrt(2)

            assert (integral - self.asg.amplitude)/self.asg.amplitude<0.01, \
                integral

    def test_iq_filter_white_noise(self):
        """
        Measure the transfer function of an iq filter by measuring the
        cross-spectrum between white-noise input and output
        """

        self.asg = self.pyrpl.rp.asg0
        self.asg.setup(amplitude=0.4,
                       waveform='noise',
                       trigger_source='immediately')
        self.iq = self.pyrpl.rp.iq0
        self.iq.setup(input=self.asg,
                      acbandwidth=0,
                      gain=1.0,
                      bandwidth=37.94,
                      frequency=1e5,
                      output_signal='output_direct')

        self.sa = self.pyrpl.spectrumanalyzer
        self.sa.setup(input1_baseband=self.asg,
                      span=125e6)
        curve = self.sa.single()
        # still to be implemented

    def test_flatness_iqmode(self):
        return # to be tested in next release
        for span in [5e4, 1e5, 5e5, 1e6, 2e6]:
            self.pyrpl.spectrumanalyzer.setup(baseband=False,
                                              center=1e5,
                                              span=span,
                                              input="asg0",
                                              running_state='stopped')
            asg = self.pyrpl.rp.asg0
            asg.setup(frequency=1e5,
                      amplitude=1,
                      trigger_source='immediately',
                      offset=0,
                      waveform='sin')
            freqs = np.linspace(1e5, 9e5)
            points = []
            for freq in freqs:
                asg.frequency = freq
                curve = self.pyrpl.spectrumanalyzer.curve()
                points.append(max(curve))
                assert abs(max(curve) - 1) < 0.01, max(curve)

    def test_save_curve(self):
        sa = self.pyrpl.spectrumanalyzer
        sa.setup(baseband=True,
                      center=0,
                      window='flattop',
                      span=1e6,
                      input1_baseband="asg0",
                      running_state='stopped')
        sa.single()
        curves = sa.save_curve()
        assert (curves[0].data[1]==sa.data_avg[0]).all()
        self.curves += curves  # curves will be deleted by teardownAll
