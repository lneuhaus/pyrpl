import os.path as osp

from pyrpl.pyrpl_utils import MyDoubleSpinBox
from pyrpl.gui.redpitaya_gui import ModuleWidget
from PyQt4 import QtCore, QtGui

IMAGE_PATH = osp.join(osp.dirname(__file__), "images")


class MyLabelSignal(QtGui.QLabel):
    pass

"""
class WidgetProp(QtGui.QFrame):
    def __init__(self, label, widget):
        super(WidgetProp, self).__init__()
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)
        self.label = label
        self.widget = widget
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.widget)
        self.setStyleSheet("WidgetProp{border: 1px solid black; border-radius: 10px; content-margins: 0,0,0,0}")
        #self.setStyleSheet("QFrame{ border: 1px solid black; border-radius: 5px }")
        #"background-color:white;")
"""


class MyItem(QtGui.QLabel):
    def __init__(self, widget_name, y, label, parent, x_offset=0):
        super(MyItem, self).__init__(label)
        self.widget_name = widget_name
        self.y = y
        self.x_offset = x_offset
        self.parent = parent
        parent.graphic_items.append(self)
        self.setStyleSheet(
            "QLabel{border: 1px solid black; border-radius: 5px; font-size: 15px; background-color:white}")
        self.proxy = parent.scene.addWidget(self)
        self.proxy.setZValue(2)

    def move_to_right_position(self):
        widget = self.parent.iq_widgets[0].properties[self.widget_name].widget
        x = widget.pos().x() + widget.width()/2 + self.x_offset - self.width()/2
        y = self.y*self.parent.view.height() - self.height()/2
        self.move(x, y)



class MyLabel(MyItem):
    pass


class MyImage(MyItem):
    def __init__(self, widget_name, y, filename, parent, x_offset=0):
        super(MyImage, self).__init__(widget_name, y, "", parent, x_offset)
        self.pixmap = QtGui.QPixmap(osp.join(IMAGE_PATH, filename))
        self.setPixmap(self.pixmap)
        self.setFixedSize(self.pixmap.size())

class Connection(object):
    arrow_height = 10
    arrow_width = 15
    margin = 15

    def __init__(self, widget1, widget2, h_first, parent, show_arrow=True):
        self.parent = parent
        self.widget_start = widget1
        self.widget_stop = widget2
        self.h_first = h_first
        self.show_arrow = show_arrow

        self.brush = QtGui.QBrush(QtCore.Qt.black)
        self.arrow = QtGui.QGraphicsPolygonItem()
        self.arrow.setBrush(self.brush)
        self.pen = QtGui.QPen(QtCore.Qt.black,
                                      3,
                                      QtCore.Qt.SolidLine,
                                      QtCore.Qt.RoundCap,
                                      QtCore.Qt.RoundJoin)


        self.line1 = QtGui.QGraphicsLineItem()
        self.line1.setPen(self.pen)
        self.line2 = QtGui.QGraphicsLineItem()
        self.line2.setPen(self.pen)
        self.line1.setZValue(1)
        self.line2.setZValue(1)

        self.parent.scene.addItem(self.line1)
        self.parent.scene.addItem(self.line2)
        self.parent.scene.addItem(self.arrow)
        self.adjust()

    def adjust(self):
        x1 = self.widget_start.pos().x() + self.widget_start.width() / 2
        x2 = self.widget_stop.pos().x() + self.widget_stop.width() / 2
        y1 = self.widget_start.pos().y() + self.widget_start.height() / 2
        y2 = self.widget_stop.pos().y() + self.widget_stop.height() / 2
        if self.h_first:
            self.line1.setLine(x1, y1, x1, y2)
            self.line2.setLine(x1, y2, x2, y2)
        else:
            self.line1.setLine(x1, y1, x2, y1)
            self.line2.setLine(x2, y1, x2, y2)
        if self.show_arrow:
            if self.h_first:
                x = x2 - self.widget_stop.width() / 2
                y = y2
                arrow = QtGui.QPolygonF(
                    [QtCore.QPoint(x - self.margin, y - self.arrow_height / 2),
                     QtCore.QPoint(x - self.margin, y + self.arrow_height / 2),
                     QtCore.QPoint(x - self.margin + self.arrow_width, y)])
            else:
                x = x2
                y = y2  - self.widget_stop.height() / 2
                if y2<y1:
                    margin = - self.margin
                    arrow_width = - self.arrow_width
                    y = y2 + self.widget_stop.height() / 2
                else:
                    margin = self.margin
                    arrow_width = self.arrow_width
                arrow = QtGui.QPolygonF(
                    [QtCore.QPoint(x - self.arrow_height / 2, y - margin),
                     QtCore.QPoint(x + self.arrow_height / 2, y - margin),
                     QtCore.QPoint(x, y - margin + arrow_width)])

            if self.show_arrow:
                self.arrow.setPolygon(arrow)
    """
        def paint(self, painter, style, widget):


            painter.drawLine(QtCore.QLine(x1, y1, x1, y2))
            painter.drawLine(QtCore.QLine(x1, y2, x2, y2))

            painter.setBrush(QtCore.Qt.black)
            arrow =
            painter.drawPolygon(arrow)
    """

class MyFrame(QtGui.QFrame):
    def __init__(self ,parent):
        super(MyFrame, self).__init__(parent)
        self.setStyleSheet("background-color: white;")
        self.parent = parent
        self.lower()
        #self.proxy = self.parent.scene.addWidget(self)
        #self.proxy.setZValue(-1)

class MyFrameDrawing(QtGui.QFrame):
    def __init__(self , parent):
        super(MyFrameDrawing, self).__init__()
        self.setStyleSheet("background-color: white;")
        self.parent = parent
        self.lower()
        self.proxy = self.parent.scene.addWidget(self)
        self.proxy.setZValue(-1)

class AllIqWidgets(QtGui.QWidget):
    """
    The Tab widget containing all the Iqs
    """

    def __init__(self, parent=None, rp=None):
        super(AllIqWidgets, self).__init__(parent)
        self.rp = rp
        self.iq_widgets = []
        self.layout = QtGui.QVBoxLayout()
        self.setLayout(self.layout)
        nr = 0
        self.layout.setAlignment(QtCore.Qt.AlignTop)

        while hasattr(self.rp, "iq" + str(nr)):
            widget = IqWidget(name="iq" + str(nr),
                            rp=self.rp,
                            parent=None,
                            module=getattr(self.rp, "iq" + str(nr)))
            self.iq_widgets.append(widget)
            self.layout.addWidget(widget)
            nr += 1
            self.layout.setStretchFactor(widget, 0)
        self.scene = QtGui.QGraphicsScene()
        self.view = QtGui.QGraphicsView(self.scene)
        self.view.setMinimumHeight(150)
        col = self.palette().background().color().name()
        self.view.setStyleSheet("border: 0px; background-color: " + col)
        self.layout.addWidget(self.view)
        self.make_drawing()
        self.adjust_drawing()

    def adjust_drawing(self):
        for item in self.graphic_items:
            item.move_to_right_position()
        for conn in self.connections:
            conn.adjust()
        iq = self.iq_widgets[0]

        for index, prop in enumerate(["input", "acbandwidth", "frequency",
                     "bandwidth", "quadrature_factor", "gain",
                     "amplitude", "output_direct"][::2]):
            widget = iq.properties[prop].widget
            self.frames[index].setFixedSize(widget.width() + iq.main_layout.spacing(), self.height())
            self.frames[index].move(widget.x() + iq.pos().x() - iq.main_layout.spacing()/2, 0)

            self.frames_drawing[index].setFixedSize(widget.width() + iq.main_layout.spacing(), self.height())
            self.frames_drawing[index].move(widget.x() + iq.pos().x() - self.view.pos().x() - iq.main_layout.spacing()/2, 0)
        self.scene.setSceneRect(QtCore.QRectF(self.view.rect()))


    def make_drawing(self):
        brush = QtGui.QBrush(QtCore.Qt.black)

        row_center = 0.55
        row_up = 0.3
        row_down = 0.8
        row_top = 0.15
        row_center_up = 0.47
        row_center_down = 0.63
        self.graphic_items = []
        self.input = MyLabel("input", row_center, "input", parent=self)

        self.high_pass = MyImage('acbandwidth', row_center, "high_pass.bmp", parent=self)
        self.low_pass1 = MyImage('bandwidth', row_up, "low_pass.bmp", parent=self, x_offset=-40)
        self.low_pass2 = MyImage('bandwidth', row_down, "low_pass.bmp", parent=self, x_offset=-40)

        self.x_sin1 = MyLabel("frequency", row_up, "x sin", parent=self)
        self.x_cos1 = MyLabel("frequency", row_down, "x cos", parent=self)
        self.x_sin2 = MyLabel("amplitude", row_up, "x sin", parent=self, x_offset=40)
        self.x_cos2 = MyLabel("amplitude", row_down, "x cos", parent=self, x_offset=40)

        self.na_real = MyLabel("bandwidth", row_center_up, "na real", parent=self, x_offset=20)
        self.na_imag = MyLabel("bandwidth", row_center_down, "na imag", parent=self, x_offset=20)

        self.x_1 = MyLabel("quadrature_factor", row_top, "X", parent=self)
        self.x_2 = MyLabel("gain", row_up, "X", parent=self)
        self.x_3 = MyLabel('gain', row_down, "X", parent=self)

        self.plus = MyLabel("amplitude", row_up, "+", parent=self, x_offset=0)

        self.cte = MyLabel("amplitude", row_center, "Cte", parent=self, x_offset=0)

        self.plus_2 = MyLabel("amplitude", row_center, "+", parent=self, x_offset=40)

        self.output_direct = MyLabel("output_signal", row_center, "output\ndirect", parent=self)
        self.output_signal = MyLabel("output_signal", row_top, "output\nsignal", parent=self)

        self.connections = []
        self.connect(self.input, self.high_pass)
        self.connect(self.high_pass, self.x_sin1)
        self.connect(self.high_pass, self.x_cos1)
        self.connect(self.x_sin1, self.low_pass1)
        self.connect(self.x_cos1, self.low_pass2)
        self.connect(self.low_pass1, self.na_real, h_first=False)
        self.connect(self.low_pass2, self.na_imag, h_first=False)
        self.connect(self.low_pass1, self.x_1, h_first=False)
        self.connect(self.low_pass1, self.x_2)
        self.connect(self.low_pass2, self.x_3)
        self.connect(self.x_2, self.plus)
        self.connect(self.cte, self.plus, h_first=False)
        self.connect(self.plus, self.x_sin2)
        self.connect(self.x_3, self.x_cos2)
        self.connect(self.x_1, self.output_signal)
        self.connect(self.x_sin2, self.plus_2, h_first=False)
        self.connect(self.x_cos2, self.plus_2, h_first=False)
        self.connect(self.plus_2, self.output_direct)
        self.connect(self.output_direct, self.output_signal, h_first=False)

        self.frames = [MyFrame(self) for i in range(4)]
        self.frames_drawing = [MyFrameDrawing(self) for i in range(4)]






    def connect(self, widget1, widget2, h_first=True):
        self.connections.append(Connection(widget1, widget2, h_first, self))

    def resizeEvent(self, event):
        super(AllIqWidgets, self).resizeEvent(event)
        self.adjust_drawing()



class IqWidget(ModuleWidget):
    """
    Widget for the IQ module
    """

    property_names = ["input",
                      "acbandwidth",
                      "frequency",
                      "bandwidth",
                      "quadrature_factor",
                      "output_signal",
                      "gain",
                      "amplitude",
                      "phase",
                      "output_direct"]

    def init_gui(self):
        super(IqWidget, self).init_gui()
        ##Then remove properties from normal property layout
        ## We will make a more fancy one !


        for key, prop in self.properties.items():
            layout = prop.layout_v
            self.property_layout.removeItem(prop.layout_v)
            """
            prop.the_widget = WidgetProp(prop.label, prop.widget)
            if key!='bandwidth':
                prop.the_widget.setMaximumWidth(120)
            """
            #self.scene.addWidget(prop.the_widget)

        self.properties["bandwidth"].widget.set_max_cols(2)
        self.properties["frequency"].widget.setMaximum(50000000)
        self.property_layout.addLayout(self.properties["input"].layout_v)
        self.property_layout.addLayout(self.properties["acbandwidth"].layout_v)
        self.property_layout.addLayout(self.properties["frequency"].layout_v)
        self.properties["frequency"].layout_v.addLayout(self.properties["phase"].layout_v)
        self.property_layout.addLayout(self.properties["bandwidth"].layout_v)
        self.property_layout.addLayout(self.properties["quadrature_factor"].layout_v)
        self.property_layout.addLayout(self.properties["gain"].layout_v)
        self.property_layout.addLayout(self.properties["amplitude"].layout_v)
        self.property_layout.addLayout(self.properties["output_signal"].layout_v)
        self.properties["output_signal"].layout_v.addLayout(self.properties["output_direct"].layout_v)

        property_acbw = self.properties["acbandwidth"]

        def update():
            """
            Sets the gui value from the current module value

            :return:
            """

            index = list(property_acbw.options).index(int(getattr(property_acbw.module,
                                                                      property_acbw.name)))
            property_acbw.widget.setCurrentIndex(index)

        property_acbw.update = update