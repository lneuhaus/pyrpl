"""
Widget of the SignalPlotter: settings on top, the list of signals to plot on
the left and the plot of the selected signals over time on the right.
"""

import pyqtgraph as pg
from qtpy import QtCore, QtWidgets

from .base_module_widget import ModuleWidget

# well separated colours, readable on the black background, in channel order
COLORS = [
    "#ffd700",  # gold
    "#00bfff",  # sky blue
    "#ff4040",  # red
    "#40e040",  # green
    "#ff8c00",  # orange
    "#da70d6",  # orchid
    "#00e5c0",  # turquoise
    "#ffffff",  # white
    "#a0a0ff",  # lavender
    "#c0c040",  # olive
]


class SignalPlotterWidget(ModuleWidget):
    def init_gui(self):
        self.init_main_layout(orientation="vertical")
        self.init_attribute_layout()

        body = QtWidgets.QHBoxLayout()
        self.main_layout.addLayout(body)

        self._updating_channels = False
        self.channel_list = QtWidgets.QListWidget()
        self.channel_list.setToolTip("signals to plot")
        self.channel_list.setFixedWidth(110)
        for signal in self.module.signal_options:
            item = QtWidgets.QListWidgetItem(signal)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            self.channel_list.addItem(item)
        self._show_channels(self.module.channels)
        self.channel_list.itemChanged.connect(self._channels_edited)
        body.addWidget(self.channel_list)

        self.plot_widget = pg.PlotWidget()
        self.plot_item = self.plot_widget.getPlotItem()
        self.plot_item.showGrid(x=True, y=True, alpha=0.3)
        self.plot_item.setLabel("left", "signal", units="V")
        self.plot_item.addLegend(offset=(-10, 10), brush=pg.mkBrush(0, 0, 0, 170))
        # long recordings: draw only what is visible, keep the peaks
        self.plot_item.setClipToView(True)
        self.plot_item.setDownsampling(auto=True, mode="peak")
        body.addWidget(self.plot_widget, stretch=1)

        self.curves = {}
        self.new_data()
        self.status_changed(self.module.status)
        self._enable_mode_fields(self.module.mode)

    def _enable_mode_fields(self, mode):
        """Greys out the settings that do not apply to the mode."""
        for name in ["duration"]:
            self.attribute_widgets[name].setEnabled(mode == "continuous")
        for name in ["points", "trigger_source", "trigger_edge", "trigger_delay"]:
            self.attribute_widgets[name].setEnabled(mode == "triggered")

    # channel selection
    def _show_channels(self, channels):
        self._updating_channels = True
        try:
            for row in range(self.channel_list.count()):
                item = self.channel_list.item(row)
                checked = item.text() in channels
                item.setCheckState(QtCore.Qt.Checked if checked else QtCore.Qt.Unchecked)
        finally:
            self._updating_channels = False

    def _channels_edited(self, _item):
        if self._updating_channels:
            return
        self.module.channels = [
            self.channel_list.item(row).text()
            for row in range(self.channel_list.count())
            if self.channel_list.item(row).checkState() == QtCore.Qt.Checked
        ]

    def update_attribute_by_name(self, name, new_value_list):
        if name == "channels":
            self._show_channels(new_value_list[0])
            return
        super().update_attribute_by_name(name, new_value_list)
        if name == "mode":
            self._enable_mode_fields(new_value_list[0])

    # slots of the module's signal launcher
    def new_data(self):
        module = self.module
        for channel in list(self.curves):
            if channel not in module.data:
                curve = self.curves.pop(channel)
                self.plot_item.removeItem(curve)
                if self.plot_item.legend is not None:
                    self.plot_item.legend.removeItem(curve)
        for index, (channel, values) in enumerate(module.data.items()):
            if channel not in self.curves:
                color = COLORS[index % len(COLORS)]
                self.curves[channel] = self.plot_item.plot(pen=pg.mkPen(color), name=channel)
            if len(values) == len(module.times):
                self.curves[channel].setData(module.times, values)
            else:
                self.curves[channel].setData([], [])
        x_label = "time since trigger" if module.mode == "triggered" else "time"
        self.plot_item.setLabel("bottom", x_label, units="s")

    def status_changed(self, status):
        self.plot_item.setTitle(status)
