"""
This file defines some primitives to draw a circuit schematic on Widgets.
For now it is only used in IqManagerWidget.
"""

import os.path as osp
from qtpy import QtCore, QtWidgets, QtGui

IMAGE_PATH = osp.join(osp.split(osp.dirname(__file__))[0], "images")


class MyLabelSignal(QtWidgets.QLabel):
    pass


class MyItem(QtWidgets.QWidget):
    def __init__(self, widget_name, y, label, parent, x_offset=0):
        super(MyItem, self).__init__()
        self.lay = QtWidgets.QVBoxLayout()
        self.setLayout(self.lay)
        self.item = QtWidgets.QLabel(label)
        self.setStyleSheet('background-color:transparent')
        self.lay.addWidget(self.item)

        self.widget_name = widget_name
        self.y = y
        self.x_offset = x_offset
        self.parent = parent
        parent.graphic_items.append(self)
        self.item.setStyleSheet(
            "QLabel{border: 1px solid black; border-radius: 5px; "
            "font-size: 15px; background-color:white}")
        self.proxy = parent.scene.addWidget(self)
        self.proxy.setZValue(2)

    def item_x(self):
        return self.pos().x() + self.item.pos().x()

    def item_y(self):
        return self.pos().y() + self.item.pos().y()

    def move_to_right_position(self):
        widget = self.parent.module_widgets[0].attribute_widgets[
            self.widget_name]
        x = widget.pos().x() + widget.width()/2 + self.x_offset - \
            self.item.width()/2 + self.item.x()
        y = self.y*self.parent.view.height() - self.item.height()/2 + \
            self.item.y()
        self.move(int(x), int(y))


class MyLabel(MyItem):
    pass


class MyImage(MyItem):
    def __init__(self, widget_name, y, filename, label, parent, x_offset=0):
        super(MyImage, self).__init__(widget_name, y, label, parent, x_offset)
        self.pixmap = QtGui.QPixmap(osp.join(IMAGE_PATH, filename))
        self.item.setPixmap(self.pixmap)
        self.item.setFixedSize(self.pixmap.size())

        self.label = QtWidgets.QLabel(label)
        self.lay.addWidget(self.label)


        #self.setText(self.widget_name)



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
        self.arrow = QtWidgets.QGraphicsPolygonItem()
        self.arrow.setBrush(self.brush)
        self.pen = QtGui.QPen(QtCore.Qt.black,
                              3,
                              QtCore.Qt.SolidLine,
                              QtCore.Qt.RoundCap,
                              QtCore.Qt.RoundJoin)

        self.line1 = QtWidgets.QGraphicsLineItem()
        self.line1.setPen(self.pen)
        self.line2 = QtWidgets.QGraphicsLineItem()
        self.line2.setPen(self.pen)
        self.line1.setZValue(1)
        self.line2.setZValue(1)

        self.parent.scene.addItem(self.line1)
        self.parent.scene.addItem(self.line2)
        self.parent.scene.addItem(self.arrow)
        self.adjust()

    def adjust(self):
        x1 = self.widget_start.item_x() + self.widget_start.item.width() / 2
        x2 = self.widget_stop.item_x() + self.widget_stop.item.width() / 2
        y1 = self.widget_start.item_y() + self.widget_start.item.height() / 2
        y2 = self.widget_stop.item_y() + self.widget_stop.item.height() / 2
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
                    [QtCore.QPoint(int(x - self.margin), int(y - self.arrow_height / 2)),
                     QtCore.QPoint(int(x - self.margin), int(y + self.arrow_height / 2)),
                     QtCore.QPoint(int(x - self.margin + self.arrow_width), int(y))])
            else:
                x = x2
                y = y2 - self.widget_stop.height() / 2
                if y2 < y1:
                    margin = - self.margin
                    arrow_width = - self.arrow_width
                    y = y2 + self.widget_stop.height() / 2
                else:
                    margin = self.margin
                    arrow_width = self.arrow_width
                arrow = QtGui.QPolygonF(
                    [QtCore.QPoint(int(x - self.arrow_height / 2), int(y - margin)),
                     QtCore.QPoint(int(x + self.arrow_height / 2), int(y - margin)),
                     QtCore.QPoint(int(x), int(y - margin + arrow_width))])

            if self.show_arrow:
                self.arrow.setPolygon(arrow)


class MyFrame(QtWidgets.QFrame):
    def __init__(self, parent):
        super(MyFrame, self).__init__(parent)
        self.setStyleSheet("background-color: white;")
        self.parent = parent
        self.lower()


class MyFrameDrawing(QtWidgets.QFrame):
    def __init__(self, parent):
        super(MyFrameDrawing, self).__init__()
        self.setStyleSheet("background-color: white;")
        self.parent = parent
        self.lower()
        self.proxy = self.parent.scene.addWidget(self)
        self.proxy.setZValue(-1)