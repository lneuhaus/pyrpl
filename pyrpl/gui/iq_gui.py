from pyrpl.pyrpl_utils import MyDoubleSpinBox
from pyrpl.gui.redpitaya_gui import ModuleWidget
from PyQt4 import QtCore, QtGui

class MyLabelSignal(QtGui.QLabel):
    pass

class IQWidget(ModuleWidget):
    """
    Widget for the IQ module
    """

    property_names = ["input",
                      "acbandwidth",
                      "frequency",
                      "bandwidth",
                      "quadrature_factor"
                      "output_signal",
                      "gain",
                      "amplitude",
                      "phase",
                      "output_direct"]
    """
    def __init__(self):
        self.scene = QtGui.QGraphicsScene()
        super(IQWidget, self).__init__(self.scene)
        self.label_in = MyLabelSignal("in")
        self.scene.addWidget(self.label_in)
        self.label_in.move(0, 50)
        self. = QtGui.QPushButton("coucou")
        self.scene.addWidget(self.button)
    """
class Connection(QtGui.QGraphicsItem):
    arrow_height = 10
    arrow_width = 15
    margin = 15
    
    def __init__(self, widget_start, widget_stop):
    
        super(Connection, self).__init__()
        self.widget_start = widget_start
        self.widget_stop = widget_stop

    def paint(self, painter, style, widget):
        painter.setPen(QtGui.QPen(QtCore.Qt.black,
                                  5,
                                  QtCore.Qt.SolidLine,
                                  QtCore.Qt.RoundCap,
                                  QtCore.Qt.RoundJoin))
        x1 = self.widget_start.pos().x() + self.widget_start.width()/2
        x2 = self.widget_stop.pos().x() + self.widget_stop.width()/2
        y1 = self.widget_start.pos().y() + self.widget_start.height()/2
        y2 = self.widget_stop.pos().y() + self.widget_stop.height()/2
        painter.drawLine(QtCore.QLine(x1, y1, x1, y2))
        painter.drawLine(QtCore.QLine(x1, y2, x2, y2))

        painter.setBrush(QtCore.Qt.black)
        arrow = QtGui.QPolygonF([QtCore.QPoint(x2 - self.widget_start.width()/2 - self.margin, y2 - self.arrow_height/2),
                                 QtCore.QPoint(x2 - self.widget_start.width()/2 - self.margin, y2 + self.arrow_height/2),
                                 QtCore.QPoint(x2 - self.widget_start.width()/2 - self.margin+ self.arrow_width, y2)])
        painter.drawPolygon(arrow)
        

IQ_GUI = IQWidget()
IQ_GUI.show()
b = MyDoubleSpinBox("b")
b2 = MyDoubleSpinBox("b2")
b.move(100,100)
b2.move(500, 500)
it = Connection(b, b2)

IQ_GUI.scene.addItem(it)
IQ_GUI.scene.addWidget(b)
IQ_GUI.scene.addWidget(b2)
