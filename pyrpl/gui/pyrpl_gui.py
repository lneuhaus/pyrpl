from time import time

from pyrpl import RedPitaya
from pyrpl.redpitaya_modules import NotReadyError
from pyqtgraph.Qt import QtGui, QtCore
import pyqtgraph as pg
import numpy as np
from pyrpl.network_analyzer import NetworkAnalyzer





APP = QtGui.QApplication.instance()
if APP is None:
    APP = QtGui.QApplication(["pyrpl_gui"])

def property_factory(module_widget, prop):
    if hasattr(module_widget.module, prop + 's'):
        new_prop = ComboProperty(prop, module_widget)
    elif hasattr(module_widget.module, prop[:-1] + 's')\
            and (prop[:-1] + 's')!=prop: # for instance inputs for input1
        new_prop = ComboProperty(prop, module_widget, prop[:-1] + 's')
    else:
        attr = getattr(module_widget.module, prop)
        if isinstance(attr, bool):
           new_prop = BoolProperty(prop, module_widget)
        elif isinstance(attr, (int, long)):
            new_prop = IntProperty(prop, module_widget)
        else:
            new_prop = FloatProperty(prop, module_widget)
    return new_prop

class BaseProperty(object):
    def __init__(self, name, module_widget):
        self.module_widget = module_widget
        self.name = name
        self.layout_v = QtGui.QVBoxLayout()
        self.label = QtGui.QLabel(name)
        self.layout_v.addWidget(self.label)
        self.module = self.module_widget.module
        self.set_widget()
        self.layout_v.addWidget(self.widget)
        self.module_widget.property_layout.addLayout(self.layout_v)
        self.module_widget.property_watch_timer.timeout.\
                                connect(self.update_widget)
    
    def update_widget(self):
        self.widget.blockSignals(True)
        self.update()
        self.widget.blockSignals(False)

class NumberProperty(BaseProperty):
    def write(self):
        setattr(self.module, self.name, self.widget.value())
        self.module_widget.property_changed.emit()

    def update(self):
        if not self.widget.isActiveWindow():
            self.widget.setValue(self.module_value())

class IntProperty(NumberProperty):
    def set_widget(self):
        self.widget = QtGui.QSpinBox()
        self.widget.setSingleStep(1)
        self.widget.valueChanged.connect(self.write)

    def module_value(self):
        return int(getattr(self.module, self.name))

class FloatProperty(NumberProperty):
    def set_widget(self):
        self.widget = QtGui.QDoubleSpinBox()
        self.widget.setDecimals(4)
        self.widget.setSingleStep(0.01)
        self.widget.valueChanged.connect(self.write)


    def module_value(self):
        return float(getattr(self.module, self.name))
        
            
class ComboProperty(BaseProperty):
    def __init__(self, name, module_widget, defaults=None):
        if defaults is not None:
            self.defaults = defaults
        else:
            self.defaults = name + 's'
        super(ComboProperty, self).__init__(name, module_widget)

    def set_widget(self):
        self.widget = QtGui.QComboBox()
        self.widget.addItems(map(str, self.options))
        self.widget.currentIndexChanged.connect(self.write)
    
    @property
    def options(self):
        return getattr(self.module, self.defaults)
    
    def write(self):
        setattr(self.module, self.name, str(self.widget.currentText()))
        self.module_widget.property_changed.emit()
        
    def update(self):
        index = self.options.index(getattr(self.module, self.name))
        self.widget.setCurrentIndex(index)
    
class BoolProperty(BaseProperty):
    def set_widget(self):
        self.widget = QtGui.QCheckBox()
        self.widget.stateChanged.connect(self.write)
    
    def write(self):
        setattr(self.module, self.name, self.widget.checkState()==2)
        self.module_widget.property_changed.emit()

    def update(self):
        self.widget.setCheckState(getattr(self.module, self.name)*2)

class ModuleWidget(QtGui.QWidget):
    property_changed = QtCore.pyqtSignal()
    property_names = []
    def __init__(self, parent=None, module=None):
        super(ModuleWidget, self).__init__(parent)
        self.module = module
        self.init_gui()
        self.update_properties()

    def init_property_layout(self):
        self.property_watch_timer = QtCore.QTimer()
        self.property_watch_timer.setInterval(100)
        self.property_watch_timer.start()

        self.property_layout = QtGui.QHBoxLayout()
        self.main_layout.addLayout(self.property_layout)
        self.properties = []

        for prop_name in self.property_names:
            prop = property_factory(self, prop_name)
            self.properties.append(prop)

    def init_gui(self):
        raise NotImplementedError()

    def update_properties(self):
        for prop in self.properties:
            prop.update_widget()

class ScopeWidget(ModuleWidget):
    property_names = ["input1",
                      "input2",
                      "duration",
                      "average",
                      "trigger_source",
                      "threshold_ch1",
                      "threshold_ch2"]

    def display_channel(self, ch):
        try:
           self.curves[ch-1].setData(self.module.times,
                                     self.module.curve(ch))
        except NotReadyError:
            pass
        
    def display_curves(self):
        for i in (1,2):
            if self.cb_ch[i-1].checkState()==2:
                self.display_channel(i)
                self.curves[i-1].setVisible(True)
            else:
                self.curves[i-1].setVisible(False)

    def run_single(self):
        self.module.setup()
        self.plot_item.enableAutoRange('xy', True)
        self.display_curves()


    def do_run_continuous(self):
        if self.module.curve_ready():
            #print "before"
            self.display_curves()
            #print "after"
            if self.first_shot_of_continuous:
                self.first_shot_of_continuous = False
                self.plot_item.enableAutoRange('xy', False)
            #print "before setup"
            self.module.setup()
            #print "after setup"
        self.timer.start()

    def run_continuous(self):
        if str(self.button_continuous.text())\
                   =="Run continuous":
            self.button_continuous.setText("Stop")
            self.button_single.setEnabled(False)
            self.module.setup()
            self.plot_item.enableAutoRange('xy', True)
            self.first_shot_of_continuous = True
            self.timer.start()
        else:
            self.button_continuous.setText("Run continuous")
            self.timer.stop()
            self.button_single.setEnabled(True)

    def init_gui(self):
        self.ch_col = ('blue', 'red')
        self.main_layout = QtGui.QVBoxLayout()
        self.init_property_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Scope")
        self.win = pg.GraphicsWindow(title="Scope")
        self.plot_item = self.win.addPlot(title="Scope")
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_save = QtGui.QPushButton("Save curve")
        self.curves = [self.plot_item.plot(pen=color[0]) \
                       for color in self.ch_col]
        self.main_layout.addWidget(self.win)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)
        self.cb_ch = []
        for i in (1,2):
            self.cb_ch.append(QtGui.QCheckBox("Channel "+str(i)))
            self.button_layout.addWidget(self.cb_ch[-1])

        self.button_single.clicked.connect(self.run_single)
        self.button_continuous.clicked.connect(self.run_continuous)
        self.button_save.clicked.connect(self.save)
        self.timer = QtCore.QTimer()
        self.timer.setInterval(10)
        self.timer.setSingleShot(True)

        self.timer.timeout.connect(self.do_run_continuous)

        for cb, col in zip(self.cb_ch, self.ch_col):
            cb.setCheckState(2)
            cb.setStyleSheet('color: ' + col)
        for cb in self.cb_ch:
            cb.stateChanged.connect(self.display_curves)

    @property
    def params(self):
        # type: () -> dict
        return dict(average=self.module.average,
                    trigger_source=self.module.trigger_source,
                    threshold_ch1=self.module.threshold_ch1,
                    threshold_ch2=self.module.threshold_ch2,
                    input1=self.module.input1,
                    input2=self.module.input2)

    def save(self):
        from pyrpl import CurveDB
        for ch in [1,2]:
            d = self.params
            d.update(ch=ch)
            c = CurveDB.create(self.module.times,
                               self.module.curve(ch),
                               **d)


class AsgGui(ModuleWidget):
    property_names = ["waveform",
                      "scale",
                      "offset",
                      "frequency",
                      "trigger_source",
                      "output_direct"]
    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.init_property_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("Asg")
        """
        self.button_single = QtGui.QPushButton("Run single")
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.curves = [self.plot_item.plot(pen=color[0]) \
                       for color in self.ch_col]
        """
        self.main_layout.addLayout(self.button_layout)
        self.cb_ch = []
        for prop in self.properties:
            if prop.name == "frequency":
                break
        freq_spin_box = prop.widget
        freq_spin_box.setDecimals(1)
        freq_spin_box.setMaximum(100e6)
        freq_spin_box.setMinimum(-100e6)
        freq_spin_box.setSingleStep(100)
        self.property_changed.connect(self.module.setup)

class AllAsgGui(QtGui.QWidget):
    def __init__(self, parent=None, rp=None):
        super(AllAsgGui, self).__init__(parent)
        self.rp = rp
        self.asg_widgets = []
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)
        nr = 1
        self.layout.setAlignment(QtCore.Qt.AlignTop)


        while hasattr(self.rp, "asg" + str(nr)):
            widget = AsgGui(parent=None,
                    module=getattr(self.rp, "asg" + str(nr)))
            self.asg_widgets.append(widget)
            self.layout.addWidget(widget)
            nr+=1
            self.layout.setStretchFactor(widget, 0)


class NaGui(ModuleWidget):
    property_names = ["iq_name",
                      "input",
                      "output_direct",
                      "start",
                      "stop",
                      "rbw",
                      "points",
                      "amplitude",
                      "logscale",
                      "avg"]

    def init_gui(self):
        self.main_layout = QtGui.QVBoxLayout()
        self.init_property_layout()
        self.button_layout = QtGui.QHBoxLayout()
        self.setLayout(self.main_layout)
        self.setWindowTitle("NA")
        self.win = pg.GraphicsWindow(title="Amplitude")
        self.win_phase = pg.GraphicsWindow(title="Phase")
        self.plot_item = self.win.addPlot(title="Amplitude")
        self.plot_item_phase = self.win_phase.addPlot(title="Phase")
        self.plot_item_phase.setXLink(self.plot_item)
        self.button_single = QtGui.QPushButton("Run single")
        self.button_single.my_label = "Single"
        self.button_continuous = QtGui.QPushButton("Run continuous")
        self.button_continuous.my_label = "Continuous"
        self.button_restart_averaging = QtGui.QPushButton('Restart averaging')

        self.button_save = QtGui.QPushButton("Save curve")

        self.curve = self.plot_item.plot(pen='b')
        self.curve_phase = self.plot_item_phase.plot(pen='b')
        self.main_layout.addWidget(self.win)
        self.main_layout.addWidget(self.win_phase)
        self.button_layout.addWidget(self.button_single)
        self.button_layout.addWidget(self.button_continuous)
        self.button_layout.addWidget(self.button_restart_averaging)
        self.button_layout.addWidget(self.button_save)
        self.main_layout.addLayout(self.button_layout)

        self.button_single.clicked.connect(self.run_single)
        self.button_continuous.clicked.connect(self.run_continuous)
        self.button_restart_averaging.clicked.connect(self.ask_restart_and_do_it)
        self.button_save.clicked.connect(self.save)
        self.timer = QtCore.QTimer() # timer for point acquisition
        self.timer.setInterval(10)
        self.timer.setSingleShot(True)

        self.update_timer = QtCore.QTimer() # timer for plot update
        self.update_timer.setInterval(50) # 50 ms refreshrate max
        self.update_timer.timeout.connect(self.update_plot)
        self.update_timer.setSingleShot(True)

        self.continuous = True
        self.paused = True
        self.need_restart = True

        self.property_changed.connect(self.ask_restart)

        self.timer.timeout.connect(self.add_one_point)

        self.paused = True
        self.restart_averaging()

        for prop in self.properties:
            if prop.name in ["start", "stop", "rbw"]:
                spin_box = prop.widget
                #spin_box.setDecimals(1)
                spin_box.setMaximum(100e6)
                spin_box.setMinimum(-100e6)
                spin_box.setSingleStep(100)
            if prop.name in ["points", "avg"]:
                spin_box = prop.widget
                spin_box.setMaximum(1e6)
                spin_box.setMinimum(0)

    def save_current_params(self):
        self.current_params = dict(start=self.module.start,
                                   stop=self.module.stop,
                                   rbw=self.module.rbw,
                                   input=self.module.input,
                                   output_direct=self.module.output_direct,
                                   points=self.module.points,
                                   amplitude=self.module.amplitude,
                                   logscale=self.module.logscale,
                                   avg=self.module.avg,
                                   post_average=self.post_average)

    def save(self):
        from pyrpl import CurveDB
        c = CurveDB.create(self.x[:self.last_valid_point],
                           self.data[:self.last_valid_point],
                           **self.current_params)

    def init_data(self):
        self.data = np.zeros(self.module.points, dtype=complex)
        self.x = np.empty(self.module.points)
        self.phase = np.empty(self.module.points)
        self.amp_abs = np.empty(self.module.points)
        self.post_average = 0

    def ask_restart(self):
        self.set_state(continuous=self.continuous, paused=True, need_restart=True, n_av=0)

    def ask_restart_and_do_it(self):
        if not self.paused:
            self.timer.stop()
            self.restart_averaging()
            self.new_run()
            self.timer.start()
            self.set_state(continuous=self.continuous, paused=self.paused, need_restart=False, n_av=0)
        else:
            self.set_state(continuous=self.continuous, paused=self.paused, need_restart=True, n_av=0)

    def restart_averaging(self):
        self.init_data()
        self.timer.setInterval(self.module.time_per_point * 1000)
        self.update_timer.setInterval(10)
        self.new_run()

    def run_single(self):
        if self.paused:
            if self.continuous or self.need_restart:
                self.restart_averaging()
                self.new_run()
            self.set_state(continuous=False, paused=False, need_restart=False)
            self.timer.start()
        else:
            self.set_state(continuous=False, paused=True, need_restart=False)


    def new_run(self):
        self.module.setup()
        self.values = self.module.values()
        self.save_current_params()

    def set_state(self, continuous, paused, need_restart, n_av=0):
        self.continuous = continuous
        self.paused = paused
        self.need_restart = need_restart
        active_button = self.button_continuous if continuous else self.button_single
        inactive_button = self.button_single if continuous else self.button_continuous
        self.button_restart_averaging.setEnabled(not need_restart)
        active_button.setEnabled(True)
        inactive_button.setEnabled(self.paused)
        first_word = 'Run ' if need_restart else 'Continue '
        if self.paused:
            self.button_single.setText("Run single")
            self.button_continuous.setText(first_word + "(%i averages)"%n_av)
        else:
            if active_button == self.button_single:
                active_button.setText('Pause')
            else:
                active_button.setText('Pause (%i averages)'%n_av)

    @property
    def last_valid_point(self):
        if self.post_average>0:
            max_point = self.module.points
        else:
            max_point = self.module.current_point
        return max_point

    def threshold_hook(self, current_val):
        """
        A convenience function to stop the run upon some condition
        (such as reaching of a threshold. current_val is the complex amplitude
        of the last data point).

        To be overwritten in derived class...
        Parameters
        ----------
        current_val

        Returns
        -------

        """
        pass

    def update_plot(self):
        """
        Update plot only every 10 ms max...

        Returns
        -------
        """
        #plot_time_start = time()
        self.curve.setData(self.x[:self.last_valid_point],
                           self.amp_abs[:self.last_valid_point])

        self.curve_phase.setData(self.x[:self.last_valid_point],
                             self.phase[:self.last_valid_point])
        #plot_time = time() - plot_time_start # actually not working, because done latter
        #self.update_timer.setInterval(plot_time*10*1000) # make sure plotting
                                                         # is only marginally slowing
                                                         # down the measurement...
        self.update_timer.setInterval(self.last_valid_point/100)

    def add_one_point(self):
        if self.paused:
            return
        cur = self.module.current_point
        try:
            x, y, amp = self.values.next()
            self.threshold_hook(y)
        except StopIteration:
            self.post_average += 1
            if self.continuous:
                self.new_run()
                self.set_state(continuous=True, paused=False, need_restart=False, n_av=self.post_average)
                self.timer.start()
            else:
                self.set_state(continuous=True, paused=True, need_restart=False, n_av=self.post_average) # 1
                self.button_single.setText("Run single")
            return
        self.data[cur] = (self.data[cur]*self.post_average + y)/(self.post_average + 1)

        self.phase[cur] = np.angle(self.data[cur], deg=True)
        self.amp_abs[cur] = abs(self.data[cur])
        self.x[cur] = x

        if not self.update_timer.isActive():
            self.update_timer.start()

        self.timer.setInterval(self.module.time_per_point*1000)
        self.timer.start()

    def run_continuous(self):
        if self.paused:
            if self.need_restart:
                self.restart_averaging()
                self.new_run()
            self.set_state(continuous=True, paused=False, need_restart=False, n_av=self.post_average)
            self.timer.start()
        else:
            self.set_state(continuous=True, paused=True, need_restart=False, n_av=self.post_average)
    """
    def restart_averaging(self):
        self.init_data()
        self.run()
    """



class RedPitayaGui(RedPitaya):
    def __init__(self, *args, **kwds):
        super(RedPitayaGui, self).__init__(*args, **kwds)
        self.na_widget = NaGui(parent=None, module=NetworkAnalyzer(self))
        self.scope_widget = ScopeWidget(parent=None, module=self.scope)
        self.all_asg_widget = AllAsgGui(parent=None, rp=self)

        self.customize_scope()
        self.customize_na()
        self.custom_setup()

    def gui(self):
        self.gui_timer = QtCore.QTimer()
        self.tab_widget = QtGui.QTabWidget()
        self.tab_widget.addTab(self.scope_widget, "Scope")
        self.tab_widget.addTab(self.all_asg_widget, "Asg")
        self.tab_widget.addTab(self.na_widget, "NA")
        self.tab_widget.show()

    def customize_scope(self):
        """
        Convenience hook for user functionality upon subclassing RedPitayaGui
        Returns
        -------

        """

        pass

    def customize_na(self):
        """
        Convenience hook for user functionality upon subclassing RedPitayaGui
        Returns
        -------

        """

        pass


    def custom_setup(self):
        """
        Convenience hook for user functionality upon subclassing RedPitayaGui
        Returns
        -------

        """
        pass

    @property
    def na(self):
        return self.na_widget.module









