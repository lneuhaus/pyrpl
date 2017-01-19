"""
The Iir widget allows to dynamically select zeros and poles of the iir filter
"""
from .base_module_widget import ModuleWidget

from PyQt4 import QtCore, QtGui
import pyqtgraph as pg
import numpy as np


APP = QtGui.QApplication.instance()

class IirWidget(ModuleWidget):
    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.setLayout(self.main_layout)
        self.win = MyGraphicsWindow(title="Amplitude", parent_widget=self)
        self.win_phase = MyGraphicsWindow(title="Phase", parent_widget=self)
        # self.proxy = pg.SignalProxy(self.win.scene().sigMouseClicked, rateLimit=60, slot=self.mouse_clicked)
        self.plot_item = self.win.addPlot(title="Magnitude (dB)")
        self.plot_item_phase = self.win_phase.addPlot(title="Phase (deg)")
        self.plot_item_phase.setXLink(self.plot_item)
        # self.proxy_phase = pg.SignalProxy(self.win_phase.scene().sigMouseClicked, rateLimit=60, slot=self.mouse_clicked)

        self.curve = self.plot_item.plot(pen='y')
        self.curve_phase = self.plot_item_phase.plot(pen=None, symbol='o', symbolSize=1)

        self.points_poles = pg.ScatterPlotItem(size=20,
                                               symbol='x',
                                               pen=pg.mkPen(None),
                                               brush=pg.mkBrush(255, 0, 255, 120))
        self.plot_item.addItem(self.points_poles)
        self.points_poles_phase =  pg.ScatterPlotItem(size=20,
                                                      pen=pg.mkPen(None),
                                                      symbol='x',
                                                      brush=pg.mkBrush(255, 0, 255, 120))
        self.plot_item_phase.addItem(self.points_poles_phase)

        self.points_zeros = pg.ScatterPlotItem(size=20,
                                               symbol='o',
                                               pen=pg.mkPen(None),
                                               brush=pg.mkBrush(255, 0, 255, 120))
        self.plot_item.addItem(self.points_zeros)
        self.points_zeros_phase = pg.ScatterPlotItem(size=20,
                                                     pen=pg.mkPen(None),
                                                     symbol='o',
                                                     brush=pg.mkBrush(255, 0, 255, 120))
        self.plot_item_phase.addItem(self.points_zeros_phase)

        self.main_layout.addWidget(self.win)
        self.main_layout.addWidget(self.win_phase)
        self.init_attribute_layout()
        self.second_attribute_layout = QtGui.QVBoxLayout()
        self.attribute_layout.addLayout(self.second_attribute_layout)
        self.third_attribute_layout = QtGui.QVBoxLayout()
        self.attribute_layout.addLayout(self.third_attribute_layout)
        index = 0
        for key, widget in self.attribute_widgets.items():
            index+=1
            if index>3:
                layout = self.third_attribute_layout
            else:
                layout = self.second_attribute_layout
            if key!='poles' and key!='zeros':
                self.attribute_layout.removeWidget(widget)
                layout.addWidget(widget, stretch=0)

        self.second_attribute_layout.addStretch(1)
        self.third_attribute_layout.addStretch(1)
        for attribute_widget in self.attribute_widgets.values():
            self.main_layout.setStretchFactor(attribute_widget, 0)

        self.frequencies = np.logspace(1, np.log10(5e6), 2000)


        self.xlog = True
        self.curve.setLogMode(xMode=self.xlog, yMode=None)
        self.curve_phase.setLogMode(xMode=self.xlog, yMode=None)

        self.plot_item.setLogMode(x=self.xlog, y=None) # this seems also needed
        self.plot_item_phase.setLogMode(x=self.xlog, y=None)

        self.module.setup()
        self.update_plot()

        self.points_poles.sigClicked.connect(self.select_pole)
        self.points_poles_phase.sigClicked.connect(self.select_pole)

        self.points_zeros.sigClicked.connect(self.select_zero)
        self.points_zeros_phase.sigClicked.connect(self.select_zero)

    def select_pole(self, plot_item, spots):
        index = spots[0].data()
        self.attribute_widgets['poles'].set_selected(index)

    def select_zero(self, plot_item, spots):
        index = spots[0].data()
        self.attribute_widgets['zeros'].set_selected(index)

    def update_plot(self):
        tf = self.module.transfer_function(self.frequencies)
        self.curve.setData(self.frequencies, abs(tf))
        self.curve_phase.setData(self.frequencies, 180.*np.angle(tf)/np.pi)
        freq_poles = abs(np.imag(self.module.poles))
        tf_poles = self.module.transfer_function(freq_poles)  # why is frequency the imaginary part? is it
        # related to Laplace transform?
        freq_zeros = abs(np.imag(self.module.zeros))
        tf_zeros = self.module.transfer_function(freq_zeros)
        selected_pole = self.attribute_widgets["poles"].get_selected()
        brush_poles = [{True: pg.mkBrush(color='r'), False: pg.mkBrush(color='b')}[num==selected_pole] \
                                    for num in range(self.attribute_widgets["poles"].number)]
        self.points_poles_phase.setPoints([{'pos': (freq, phase), 'data': index, 'brush': brush} for (index, (freq, phase, brush)) in \
                                     enumerate(zip(np.log10(freq_poles), 180./np.pi*np.angle(tf_poles), brush_poles))])
        self.points_poles.setPoints([{'pos': (freq, mag), 'data': index, 'brush': brush} for (index, (freq, mag, brush)) in \
                                                            enumerate(zip(np.log10(freq_poles), abs(tf_poles), brush_poles))])

        selected_zero = self.attribute_widgets["zeros"].get_selected()
        brush_zeros = [{True: pg.mkBrush(color='r'), False: pg.mkBrush(color='b')}[num==selected_zero] \
                                    for num in range(self.attribute_widgets["zeros"].number)]
        self.points_zeros_phase.setPoints(
            [{'pos': (freq, phase), 'data': index, 'brush': brush} for (index, (freq, phase, brush)) in \
             enumerate(zip(np.log10(freq_zeros), 180. / np.pi * np.angle(tf_zeros), brush_zeros))])
        self.points_zeros.setPoints([{'pos': (freq, mag), 'data': index, 'brush': brush} for (index, (freq, mag, brush)) in \
                                     enumerate(zip(np.log10(freq_zeros), abs(tf_zeros), brush_zeros))])
