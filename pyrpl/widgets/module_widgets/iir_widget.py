"""
The Iir widget allows to dynamically select zeros and poles of the iir filter
"""
from .base_module_widget import ModuleWidget
from collections import OrderedDict
from qtpy import QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np
import sys
from ... import APP

class MyGraphicsWindow(pg.GraphicsWindow):
    def __init__(self, title, parent):
        super(MyGraphicsWindow, self).__init__(title)
        self.parent = parent
        self.setToolTip("-----plot legend---------------\n"
                        "yellow: theoretical IIR transfer function\n"
                        "green: data curve\n"
                        "red: inverse IIR transfer function /\n"
                        "-----shortcuts-----------------\n"
                        "CTRL + Left click: add one more pole. \n"
                        "SHIFT + Left click: add one more zero\n"
                        "Left Click: select pole (other possibility: click on the '+j' labels below the graph)\n"
                        "Left/Right arrows: change imaginary part (frequency) of the current pole or zero\n"
                        "Up/Down arrows; change the real part (width) of the current pole or zero. \n"
                        "Poles are represented by 'X', zeros by 'O', complex one have larger symbols than real ones.")
        self.doubleclicked = False
        #APP.setDoubleClickInterval(300)  # default value (550) is fine
        self.mouse_clicked_timer = QtCore.QTimer()
        self.mouse_clicked_timer.setSingleShot(True)
        self.mouse_clicked_timer.setInterval(APP.doubleClickInterval())
        self.mouse_clicked_timer.timeout.connect(self.mouse_clicked)

    # see https://wiki.python.org/moin/PyQt/Distinguishing%20between%20click%20and%20double%20click
    # "The trick is to realise that Qt delivers MousePress, MouseRelease,
    # MouseDoubleClick and MouseRelease events in that order to the widget."
    def mousePressEvent(self, event):
        self.doubleclicked = False
        self.storeevent(event)
        if self.button == QtCore.Qt.LeftButton and self.modifier == 0:  # left button, no key
            self.parent.module.select_pole_or_zero(self.x)
        if not self.mouse_clicked_timer.isActive():
            self.mouse_clicked_timer.start()
        return super(MyGraphicsWindow, self).mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.doubleclicked = True
        self.storeevent(event)
        if self.mouse_clicked_timer.isActive():
            self.mouse_clicked_timer.stop()
            self.mouse_clicked()
        return super(MyGraphicsWindow, self).mouseDoubleClickEvent(event)

    def storeevent(self, event):
        self.button = event.button()
        self.modifier = int(event.modifiers())
        it = self.getItem(0, 0)
        pos = it.mapToScene(event.pos()) #  + it.vb.pos()
        point = it.vb.mapSceneToView(pos)
        self.x, self.y = point.x(), point.y()
        if self.parent.xlog:
            self.x = 10 ** self.x  # takes logscale into account

    def mouse_clicked(self):
        # select nearest pole/zero with a simple click, even if something else is to happen after
        default_damping = self.x/10.0
        if self.button == QtCore.Qt.LeftButton:
            if self.doubleclicked:
                new = -default_damping - 1.j * self.x
                if self.modifier == QtCore.Qt.CTRL:
                    self.parent.module.complex_poles.append(new)
                if self.modifier == QtCore.Qt.SHIFT:
                    self.parent.module.complex_zeros.append(new)
            else:  # single click
                new = -self.x
                if self.modifier == 0:
                    pass # see above in mousePressEvent()
                if self.modifier == QtCore.Qt.CTRL:
                    # make a new real pole
                    self.parent.module.real_poles.append(new)
                if self.modifier == QtCore.Qt.SHIFT:
                    # make a new real zero
                    self.parent.module.real_zeros.append(new)

    def keyPressEvent(self, event):
        """ not working properly yet"""
        try:
            name = self.parent.module._selected_pole_or_zero
            index = self.parent.module._selected_index
            return self.parent.parent.attribute_widgets[name].widgets[index].keyPressEvent(event)
        except:
            return super(MyGraphicsWindow, self).keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """ not working properly yet"""
        def keyPressEvent(self, event):
            try:
                name = self.parent.module._selected_pole_or_zero
                index = self.parent.module._selected_index
                return self.parent.parent.attribute_widgets[name].widgets[index].keyReleaseEvent(event)
            except:
                return super(MyGraphicsWindow, self).keyReleaseEvent(event)


class IirGraphWidget(QtWidgets.QGroupBox):
    # whether xaxis is plotted in log-scale
    xlog = True

    def __init__(self, parent):
        # graph
        self.name = "Transfer functions"
        super(IirGraphWidget, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        self.layout = QtWidgets.QVBoxLayout(self)
        self.win = MyGraphicsWindow(title="Amplitude", parent=self)
        self.win_phase = MyGraphicsWindow(title="Phase", parent=self)
        # self.proxy = pg.SignalProxy(self.win.scene().sigMouseClicked,
        # rateLimit=60, slot=self.mouse_clicked)
        self.mag = self.win.addPlot(title="Magnitude (dB)")
        self.phase = self.win_phase.addPlot(title="Phase (deg)")
        self.phase.setXLink(self.mag)
        # self.proxy_phase = pg.SignalProxy(self.win_phase.scene().sigMouseClicked,
        # rateLimit=60, slot=self.mouse_clicked)

        # we will plot the following curves:
        # poles, zeros -> large dots and crosses
        # design (designed filter) - yellow line
        # measured filter with na - orange dots
        # data (measruement data) - green line
        # data x design (or data/design) - red line
        self.plots = OrderedDict()

        # make scatterplot items
        for name, style in [('filter_measurement', dict(pen=pg.mkPen(None),
                                                        symbol='o',
                                                        size=5,
                                                        brush=pg.mkBrush(255, 100, 0, 180))),
                            ('zeros', dict(pen=pg.mkPen(None),
                                           symbol='o',
                                           size=10,
                                           brush=pg.mkBrush(255, 0, 255, 120))),
                            ('poles', dict(pen=pg.mkPen(None),
                                           symbol='x',
                                           size=10,
                                           brush=pg.mkBrush(255, 0, 255, 120))),
                            # ('actpole', dict(size=30,
                            #                symbol='x',
                            #                pen='r',
                            #                brush=pg.mkBrush(255, 0, 255,
                            #                                 120))),
                            # ('actzero', dict(size=30,
                            #                symbol='o',
                            #                pen='r',
                            #                brush=pg.mkBrush(255, 0, 255,
                            #                                 120)))
                            ]:
                item = pg.ScatterPlotItem(**style)
                self.mag.addItem(item)
                self.plots[name] = item
                item = pg.ScatterPlotItem(**style)
                self.phase.addItem(item)
                self.plots[name+'_phase'] = item

        # make lines
        for name, style in [('data', dict(pen='g')),
                            ('filter_design', dict(pen='y')),
                            ('data_x_design', dict(pen='r'))]:
            self.plots[name] = self.mag.plot(**style)
            self.plots[name + "_phase"] = self.phase.plot(**style)
            self.plots[name].setLogMode(xMode=self.xlog, yMode=None)
            self.plots[name + '_phase'].setLogMode(xMode=self.xlog, yMode=None)

        # also set logscale for the xaxis
        # make scatter plots
        self.mag.setLogMode(x=self.xlog, y=None)
        self.phase.setLogMode(x=self.xlog, y=None)
        self.layout.addWidget(self.win)
        self.layout.addWidget(self.win_phase)
        # connect signals
        #self.plots['poles'].sigClicked.connect(self.parent.select_pole)
        #self.plots['poles_phase'].sigClicked.connect(self.parent.select_pole)
        #self.plots['zeros'].sigClicked.connect(self.parent.select_zero)
        #self.plots['zeros_phase'].sigClicked.connect(self.parent.select_zero)


class IirButtonWidget(QtWidgets.QGroupBox):
    BUTTONWIDTH = 120

    def __init__(self, parent):
        # buttons and standard attributes
        self.name = "General settings"
        super(IirButtonWidget, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        self.layout = QtWidgets.QVBoxLayout(self)
        #self.setLayout(self.layout)  # wasnt here before
        aws = self.parent.attribute_widgets

        for attr in ['input', 'inputfilter', 'output_direct', 'loops',
                     'gain', 'on', 'bypass', 'overflow']:
            widget = aws[attr]
            widget.setFixedWidth(self.BUTTONWIDTH)
            self.layout.addWidget(widget)

        self.setFixedWidth(self.BUTTONWIDTH+30)


class IirBottomWidget(QtWidgets.QGroupBox):
    BUTTONWIDTH = 300

    def __init__(self, parent):
        # widget for poles and zeros
        self.name = "Filter poles and zeros"
        super(IirBottomWidget, self).__init__(parent)
        self.parent = parent
        self.module = self.parent.module
        self.layout = QtWidgets.QHBoxLayout(self)
        #self.setLayout(self.layout)  # wasnt here before
        aws = self.parent.attribute_widgets
        for attr in ['complex_poles', 'complex_zeros',
                     'real_poles', 'real_zeros']:
            widget = aws[attr]
            widget.setFixedWidth(self.BUTTONWIDTH)
            self.layout.addWidget(widget)


class IirWidget(ModuleWidget):
    def init_gui(self):
        # setup filter in its present state
        self.module.setup() # moved at the beginning of the function,
        # otherwise, values altered in setup (such as iir.loops) are
        # not updated in the gui (gui already creted but not yet connected
        # to the signal launcher)

        self.init_main_layout(orientation="vertical")
        #self.main_layout = QtWidgets.QVBoxLayout()
        #self.setLayout(self.main_layout)

        # add all attribute widgets and remove them right away
        self.init_attribute_layout()
        for widget in self.attribute_widgets.values():
            self.main_layout.removeWidget(widget)

        # divide into top and bottom layout
        self.top_layout = QtWidgets.QHBoxLayout()
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

        # set colors of labels to the one of the corresponding traces
        self.attribute_widgets['data_curve'].setStyleSheet("color: green")
        self.attribute_widgets['data_curve_name'].setStyleSheet("color: green")

        # make curve_name read-only
        self.attribute_widgets['data_curve_name'].widget.setReadOnly(True)

        self.update_plot()

    def select_pole(self, plot_item, spots):
        index = spots[0].data()
        self.attribute_widgets['poles'].set_selected(index)

    def select_zero(self, plot_item, spots):
        index = spots[0].data()
        self.attribute_widgets['zeros'].set_selected(index)

    @property
    def frequencies(self):
        try:
            f, _ = self.module._data_curve_object.data
        except AttributeError:
            # in case data_curve is None (no curve selected)
            return np.logspace(1, np.log10(5e6), 2000)
        else:
            # avoid zero frequency (log plot)
            f[f<=0] = sys.float_info.epsilon
            return np.asarray(f, dtype=float)

    def _magnitude(self, data):
        return 20. * np.log10(np.abs(np.asarray(data, dtype=np.complex))
                              + sys.float_info.epsilon)

    def _phase(self, data):
        return np.angle(np.asarray(data, dtype=np.complex), deg=True)

    def update_plot(self):
        # first, we compile the line plot data, then we iterate over them and
        # plot them. we then plot the scatter plots in the same manner
        tfargs = {}  # args to the call of iir.transfer_function
        frequencies = self.frequencies
        plot = OrderedDict()
        # plot data curve (measurement)
        try:
            _, plot['data'] = self.module._data_curve_object.data
        except AttributeError:  # no curve for plotting available
            plot['data'] = []
        # plot designed filter
        plot['filter_design'] = self.module.transfer_function(frequencies, **tfargs)
        # plot product
        plot['data_x_design'] = []
        if self.module.plot_data_times_filter:
            try:
                plot['data_x_design'] = plot['data'] * plot['filter_design']
            except ValueError:
                pass
        # disable data plot if this is desired
        if not self.module.plot_data:
            plot['data'] = []
        # plot everything (all lines) up to here
        for k, v in plot.items():
            self.graph_widget.plots[k].setData(frequencies[:len(v)],
                                               self._magnitude(v))
            self.graph_widget.plots[k+'_phase'].setData(frequencies[:len(v)],
                                                    self._phase(v))
        # plot poles and zeros
        aws = self.attribute_widgets
        for end in ['poles', 'zeros']:
            mag, phase = [], []
            for start in ['complex', 'real']:
                key = start+'_'+end
                freq = getattr(self.module, key)
                if start == 'complex':
                    freq = np.imag(freq)
                    defsize = 15  # complex (double) PZ's are plotted with larger symbols
                else:
                    defsize = 10
                freq = np.abs(freq)
                tf = self.module.transfer_function(freq, **tfargs)
                selected = aws[key].attribute_value.selected
                brush = [pg.mkBrush(color='m')
                         if (num == selected)
                         else pg.mkBrush(color='y')
                         for num in range(aws[key].number)]
                size = [defsize*1.0 if (num == selected) else defsize
                         for num in range(aws[key].number)]
                mag += [{'pos': (fr, val), 'data': i, 'brush': br, 'size': si}
                 for (i, (fr, val, br, si))
                 in enumerate(zip(list(np.log10(freq)),
                                  list(self._magnitude(tf)),
                                  brush,
                                  size))]
                phase += [{'pos': (fr, val), 'data': i, 'brush': br, 'size': si}
                 for (i, (fr, val, br, si))
                 in enumerate(zip(list(np.log10(freq)),
                                  list(self._phase(tf)),
                                  brush,
                                  size))]
            self.graph_widget.plots[end].setPoints(mag)
            self.graph_widget.plots[end+'_phase'].setPoints(phase)
        # plot the measurement data if desired
        if self.module.plot_measurement and hasattr(self.module, '_measurement_data'):
            f, v = self.module._measurement_data
            f[f<=0] = sys.float_info.epsilon
            f = np.asarray(np.log10(f), dtype=float)
            self.graph_widget.plots['filter_measurement'].setData(x=f[:len(v)],
                                                                  y=self._magnitude(v))
            self.graph_widget.plots['filter_measurement_phase'].setData(x=f[:len(v)],
                                                                        y=self._phase(v))

    def keyPressEvent(self, event):
        """ not working properly yet"""
        try:
            name = self.module._selected_pole_or_zero
            index = self.module._selected_index
            return self.attribute_widgets[name].widgets[index].keyPressEvent(event)
        except:
            return super(MyGraphicsWindow, self).keyPressEvent(event)

    def keyReleaseEvent(self, event):
        """ not working properly yet"""
        def keyPressEvent(self, event):
            try:
                name = self.module._selected_pole_or_zero
                index = self.module._selected_index
                return self.attribute_widgets[name].widgets[index].keyReleaseEvent(event)
            except:
                return super(MyGraphicsWindow, self).keyReleaseEvent(event)
