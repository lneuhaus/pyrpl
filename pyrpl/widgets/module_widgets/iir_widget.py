"""
The Iir widget allows to dynamically select zeros and poles of the iir filter
"""
from .base_module_widget import ModuleWidget

from PyQt4 import QtCore, QtGui
import pyqtgraph as pg
import numpy as np


APP = QtGui.QApplication.instance()


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
        return super(MyGraphicsWindow, self).mousePressEvent(*args, **kwds)


class IirGraphWidget(QtGui.QGroupBox):
    def __init__(self, parent):
        # graph
        self.name = "Transfer functions"
        super(IirGraphWidget, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        self.layout = QtGui.QVBoxLayout(self)
        self.win = MyGraphicsWindow(title="Amplitude", parent_widget=self)
        self.win_phase = MyGraphicsWindow(title="Phase", parent_widget=self)
        # self.proxy = pg.SignalProxy(self.win.scene().sigMouseClicked,
        # rateLimit=60, slot=self.mouse_clicked)
        self.plot_item = self.win.addPlot(title="Magnitude (dB)")
        self.plot_item_phase = self.win_phase.addPlot(title="Phase (deg)")
        self.plot_item_phase.setXLink(self.plot_item)
        # self.proxy_phase = pg.SignalProxy(self.win_phase.scene().sigMouseClicked,
        # rateLimit=60, slot=self.mouse_clicked)

        self.curve = self.plot_item.plot(pen='y')
        self.curve_phase = self.plot_item_phase.plot(pen=None, symbol='o',
                                                     symbolSize=1)

        self.points_poles = pg.ScatterPlotItem(size=20,
                                               symbol='x',
                                               pen=pg.mkPen(None),
                                               brush=pg.mkBrush(255, 0, 255, 120))
        self.plot_item.addItem(self.points_poles)
        self.points_poles_phase = pg.ScatterPlotItem(size=20,
                                                     pen=pg.mkPen(None),
                                                     symbol='x',
                                                     brush=pg.mkBrush(255, 0, 255,
                                                                      120))
        self.plot_item_phase.addItem(self.points_poles_phase)

        self.points_zeros = pg.ScatterPlotItem(size=20,
                                               symbol='o',
                                               pen=pg.mkPen(None),
                                               brush=pg.mkBrush(255, 0, 255, 120))
        self.plot_item.addItem(self.points_zeros)
        self.points_zeros_phase = pg.ScatterPlotItem(size=20,
                                                     pen=pg.mkPen(None),
                                                     symbol='o',
                                                     brush=pg.mkBrush(255, 0, 255,
                                                                      120))
        self.plot_item_phase.addItem(self.points_zeros_phase)
        self.layout.addWidget(self.win)
        self.layout.addWidget(self.win_phase)

        # actual plotting parameters
        self.frequencies = np.logspace(1, np.log10(5e6), 2000)
        self.xlog = True
        self.curve.setLogMode(xMode=self.xlog, yMode=None)
        self.curve_phase.setLogMode(xMode=self.xlog, yMode=None)
        self.plot_item.setLogMode(x=self.xlog, y=None)
        self.plot_item_phase.setLogMode(x=self.xlog, y=None)
        # update the plot
        self.update_plot()
        # connect signals
        self.points_poles.sigClicked.connect(self.parent.select_pole)
        self.points_poles_phase.sigClicked.connect(self.parent.select_pole)
        self.points_zeros.sigClicked.connect(self.parent.select_zero)
        self.points_zeros_phase.sigClicked.connect(self.parent.select_zero)

    def update_plot(self):
        aws = self.parent.attribute_widgets
        tf = self.module.transfer_function(self.frequencies)
        self.curve.setData(self.frequencies, abs(tf))
        self.curve_phase.setData(self.frequencies, 180. * np.angle(tf) / np.pi)
        freq_poles = abs(np.imag(self.module.poles))
        tf_poles = self.module.transfer_function(
            freq_poles)  # why is frequency the imaginary part? is it
        # related to Laplace transform?
        freq_zeros = abs(np.imag(self.module.zeros))
        tf_zeros = self.module.transfer_function(freq_zeros)
        selected_pole = aws["poles"].get_selected()
        brush_poles = [{True: pg.mkBrush(color='r'), False: pg.mkBrush(color='b')}
                       [num==selected_pole] for num in range(aws["poles"].number)]
        self.points_poles_phase.setPoints(
            [{'pos': (freq, phase), 'data': index, 'brush': brush} for
             (index, (freq, phase, brush)) in \
             enumerate(zip(np.log10(freq_poles), 180. / np.pi * np.angle(tf_poles),
                           brush_poles))])
        self.points_poles.setPoints(
            [{'pos': (freq, mag), 'data': index, 'brush': brush} for
             (index, (freq, mag, brush)) in \
             enumerate(zip(np.log10(freq_poles), abs(tf_poles), brush_poles))])

        selected_zero = aws["zeros"].get_selected()
        brush_zeros = [{True: pg.mkBrush(color='r'), False: pg.mkBrush(color='b')}[
                           num == selected_zero] \
                       for num in range(aws['zeros'].number)]
        self.points_zeros_phase.setPoints(
            [{'pos': (freq, phase), 'data': index, 'brush': brush} for
             (index, (freq, phase, brush)) in \
             enumerate(zip(np.log10(freq_zeros), 180. / np.pi * np.angle(tf_zeros),
                           brush_zeros))])
        self.points_zeros.setPoints(
            [{'pos': (freq, mag), 'data': index, 'brush': brush} for
             (index, (freq, mag, brush)) in \
             enumerate(zip(np.log10(freq_zeros), abs(tf_zeros), brush_zeros))])


class IirButtonWidget(QtGui.QGroupBox):
    BUTTONWIDTH = 100

    def __init__(self, parent):
        # buttons and standard attributes
        self.name = "General settings"
        super(IirButtonWidget, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        self.layout = QtGui.QVBoxLayout(self)
        #self.setLayout(self.layout)  # wasnt here before
        aws = self.parent.attribute_widgets

        for attr in ['input', 'inputfilter', 'output_direct', 'loops',
                     'gain', 'on', 'bypass', 'overflow']:
            widget = aws[attr]
            widget.setFixedWidth(self.BUTTONWIDTH)
            self.layout.addWidget(widget)

        self.setFixedWidth(self.BUTTONWIDTH+50)


class IirBottomWidget(QtGui.QGroupBox):
    BUTTONWIDTH = 150

    def __init__(self, parent):
        # widget for poles and zeros
        self.name = "Filter poles and zeros"
        super(IirBottomWidget, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        self.layout = QtGui.QHBoxLayout(self)
        #self.setLayout(self.layout)  # wasnt here before
        aws = self.parent.attribute_widgets
        for attr in ['poles', 'zeros']:
            widget = aws[attr]
            widget.setFixedWidth(self.BUTTONWIDTH)
            self.layout.addWidget(widget)


class IirWidget(ModuleWidget):
    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.setLayout(self.main_layout)

        # add all attribute widgets and remove them right away
        self.init_attribute_layout()
        for widget in self.attribute_widgets.values():
            self.main_layout.removeWidget(widget)

        # divide into top and bottom layout
        self.top_layout = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.top_layout)

        # add graph widget
        self.graph_widget = IirGraphWidget(self)
        self.top_layout.addWidget(self.graph_widget)

        # buttons to the right of graph
        self.button_widget = IirButtonWidget(self)
        self.top_layout.addWidget(self.button_widget)

        # poles and zeros at the bottom of the graph
        self.bottom_widget = IirBottomWidget(self)
        self.main_layout.addWidget(self.bottom_widget)

        # setup filter in its present state
        self.module.setup()

    def select_pole(self, plot_item, spots):
        index = spots[0].data()
        self.attribute_widgets['poles'].set_selected(index)

    def select_zero(self, plot_item, spots):
        index = spots[0].data()
        self.attribute_widgets['zeros'].set_selected(index)

