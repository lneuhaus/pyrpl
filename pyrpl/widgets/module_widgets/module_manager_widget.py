"""
ModuleManagerWidgets are just a frame containing several identical module widgets such as iqs, pids or asgs
"""

from .base_module_widget import ModuleWidget
from .schematics import MyLabel, MyImage, Connection, MyFrame, MyFrameDrawing

from qtpy import QtCore, QtWidgets, QtGui


class ModuleManagerWidget(ModuleWidget):
    add_stretch = True

    def create_title_bar(self):
        """
        ModuleManagerWidgets don't have a title bar
        """
        self.setStyleSheet(
            "ModuleManagerWidget{border:0;color:transparent;}")  # frames and title hidden for software_modules

    def init_gui(self):
        self.main_layout = QtWidgets.QVBoxLayout()
        self.module_widgets = []

        for index, mod in enumerate(self.module.all_modules):
            module_widget = mod._create_widget()
            # frames and titles visible only for sub-modules of Managers
            # module_widget.setStyleSheet("ModuleWidget{border: 1px dashed gray;color: black;}")
            self.module_widgets.append(module_widget)
            self.main_layout.addWidget(module_widget)
        if self.add_stretch:
            self.main_layout.addStretch(5) # streth space between Managers preferentially.
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.main_layout)

    def contextMenuEvent(self, event):
        for widget in self.module_widgets:
            if widget.geometry().contains(event.pos()):
                if widget.module.owner is not None:
                    act = QtWidgets.QAction('Free %s'%widget.module.name, self)
                    act.triggered.connect(widget.module.free)
                    menu = QtWidgets.QMenu()
                    menu.addAction(act)
                    menu.exec_(event.globalPos())


class PidManagerWidget(ModuleManagerWidget):
    pass


class AsgManagerWidget(ModuleManagerWidget):
    pass


class ScopeManagerWidget(ModuleManagerWidget):
    add_stretch = False # Scope should expand maximally


class IirManagerWidget(ModuleManagerWidget):
    pass


class IirManagerWidget(ModuleManagerWidget):
    pass

class PwmManagerWidget(ModuleManagerWidget):
    pass

class IqManagerWidget(ModuleManagerWidget):
    def init_gui(self):
        """
        In addition to the normal ModuleManagerWidget stacking of module attributes, the IqManagerWidget
        displays a schematic of the iq  module internal logic.
        """
        super(IqManagerWidget, self).init_gui()
        self.button_hide = QtWidgets.QPushButton('^', parent=self)
        self.button_hide.setMaximumHeight(15)
        self.button_hide.clicked.connect(self.button_hide_clicked)
        nr = 0
        self.main_layout.setAlignment(QtCore.Qt.AlignTop)
        self.scene = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setMinimumHeight(150)
        col = self.palette().color(self.palette().Window).name()
        self.view.setStyleSheet("border: 0px; background-color: " + col)
        self.main_layout.addWidget(self.view)
        self.make_drawing()
        self.button_hide_clicked()
        # self.adjust_drawing()

    def button_hide_clicked(self):
        if str(self.button_hide.text())=='v':
            self.button_hide.setText('^')
            for widget in self.module_widgets:
                self.main_layout.setStretchFactor(widget, 0)
            self.view.show()
            for frame in self.frames:
                frame.show()
            for frame in self.frames_drawing:
                frame.show()
            last_module_widget = self.module_widgets[-1]
            #self.setMaximumHeight(600)
        else:
            self.button_hide.setText('v')
            for widget in self.module_widgets:
                self.main_layout.setStretchFactor(widget, 1)
            self.view.hide()
            for frame in self.frames:
                frame.hide()
            for frame in self.frames_drawing:
                frame.hide()
            # last_module_widget = self.module_widgets[-1]
            # self.setMaximumHeight(last_module_widget.pos().y() + last_module_widget.height())
            # self.setMaximumHeight(600) # By calling twice, forces the window to shrink
        self.adjust_drawing()

    def adjust_drawing(self):
        """
        When the user resizes the window, the drawing elements follow the x-positions of the corresponding
        attribute_widgets.
        """

        for item in self.graphic_items:
            item.move_to_right_position()
        for conn in self.connections:
            conn.adjust()
        iq = self.module_widgets[0]

        for index, prop in enumerate(["input", "acbandwidth", "frequency",
                                      "bandwidth", "quadrature_factor", "gain",
                                      "amplitude", "output_direct"][::2]):
            widget = iq.attribute_widgets[prop]
            self.frames[index].setFixedSize(widget.width() + iq.main_layout.spacing(), self.height())
            self.frames[index].move(int(widget.x() + iq.pos().x() - iq.main_layout.spacing() / 2), 0)

            self.frames_drawing[index].setFixedSize(widget.width() + iq.main_layout.spacing(), self.height())
            self.frames_drawing[index].move(int(widget.x() + iq.pos().x() - self.view.pos().x() - iq.main_layout.spacing() / 2),
                                            0)
        self.scene.setSceneRect(QtCore.QRectF(self.view.rect()))
        #x, y = self.view.pos().x(), self.view.pos().y()
        button_width = 150
        self.button_hide.move(int(self.width()/2 - button_width/2), int(self.height() - 17))
        self.button_hide.setFixedWidth(button_width)
        self.button_hide.raise_()

    def make_drawing(self):
        """
        Uses the primitives defined in schematics.py to draw the diagram.
        """
        brush = QtGui.QBrush(QtCore.Qt.black)

        row_center = 0.45
        row_up = 0.2
        row_down = 0.7
        row_top = 0.05
        row_center_up = 0.35
        row_center_down = 0.55
        row_bottom = 0.8
        self.graphic_items = []
        self.input = MyLabel("input", row_center, "input", parent=self)

        self.high_pass = MyImage('acbandwidth', row_center,
                                 "high_pass.bmp", 'acbandwidth',
                                 parent=self, x_offset=-30)
        self.low_pass1 = MyImage('bandwidth', row_up, "low_pass.bmp",
                                 'bandwidth', parent=self, x_offset=-50)
        self.low_pass2 = MyImage('bandwidth', row_down, "low_pass.bmp",
                                 'bandwidth', parent=self, x_offset=-50)

        self.x_sin1 = MyLabel("frequency", row_center_up, "sin(wt + phi)",
                              parent=self, x_offset=-20)
        self.x_cos1 = MyLabel("frequency", row_center_down, "cos(wt + phi)",
                              parent=self, x_offset=-20)



        self.x_demod_sin = MyLabel("frequency", row_up, 'X', parent=self, x_offset=-20)
        self.x_demod_cos = MyLabel("frequency", row_down, 'X', parent=self, x_offset=-20)

        self.x_sin2 = MyLabel("amplitude", row_center_up, "X", parent=self,
                              x_offset=-40)
        self.x_cos2 = MyLabel("amplitude", row_center_down, "X", parent=self,
                              x_offset=-40)

        self.na_real = MyLabel("bandwidth", row_top, "na real", parent=self,
                               x_offset=20)
        self.na_imag = MyLabel("bandwidth", row_bottom, "na imag", parent=self,
                               x_offset=20)


        self.quad_fact = MyLabel("quadrature_factor", row_top,
                                 "quadrature_factor",
                                 parent=self, x_offset=-40)
        self.x_1 = MyLabel("quadrature_factor", row_top, "X", parent=self,
                           x_offset=40)

        self.gain = MyLabel("gain", row_center, "gain", parent=self,
                            x_offset=-20)
        self.x_2 = MyLabel("gain", row_up, "X", parent=self, x_offset=-20)
        self.x_3 = MyLabel('gain', row_down, "X", parent=self, x_offset=-20)

        self.plus = MyLabel("amplitude", row_up, "+", parent=self,
                            x_offset=-40)

        self.cte = MyLabel("amplitude", row_up, "amplitude", parent=self,
                           x_offset=20)

        self.plus_2 = MyLabel("amplitude", row_center, "+", parent=self,
                              x_offset=-40)

        self.output_direct = MyLabel("output_signal", row_center, "output\ndirect", parent=self)
        self.output_signal = MyLabel("output_signal", row_top, "output\nsignal", parent=self)

        self.connections = []
        self.connect(self.input, self.high_pass)
        self.connect(self.high_pass, self.x_demod_sin)
        self.connect(self.high_pass, self.x_demod_cos)
        self.connect(self.x_sin1, self.x_demod_sin, h_first=False)
        self.connect(self.x_cos1, self.x_demod_cos, h_first=False)
        self.connect(self.x_demod_sin, self.low_pass1)
        self.connect(self.x_demod_cos, self.low_pass2)
        self.connect(self.low_pass1, self.na_real, h_first=False)
        self.connect(self.low_pass2, self.na_imag, h_first=False)
        self.connect(self.low_pass1, self.x_1, h_first=False)


        self.connect(self.gain, self.x_2, h_first=False)
        self.connect(self.gain, self.x_3, h_first=False)
        self.connect(self.low_pass1, self.x_2)
        self.connect(self.low_pass2, self.x_3)
        self.connect(self.x_2, self.plus)
        self.connect(self.cte, self.plus)
        self.connect(self.plus, self.x_sin2, h_first=False)
        self.connect(self.x_3, self.x_cos2, h_first=False)

        self.connect(self.quad_fact, self.x_1)
        self.connect(self.x_1, self.output_signal)

        self.connect(self.x_sin1, self.x_sin2)
        self.connect(self.x_cos1, self.x_cos2)

        self.connect(self.x_sin2, self.plus_2, h_first=False)
        self.connect(self.x_cos2, self.plus_2, h_first=False)

        self.connect(self.plus_2, self.output_direct)
        self.connect(self.output_direct, self.output_signal, h_first=False)

        self.frames = [MyFrame(self) for i in range(4)]
        self.frames_drawing = [MyFrameDrawing(self) for i in range(4)]

    def connect(self, widget1, widget2, h_first=True):
        """
        Connects 2 blocks with an arrow h_first means the first line originating from widget1 is horizontal.
        """

        self.connections.append(Connection(widget1, widget2, h_first, self))

    def resizeEvent(self, event):
        """
        call adjust_drawing upon resize.
        """

        super(IqManagerWidget, self).resizeEvent(event)
        self.adjust_drawing()
