import logging
logger = logging.getLogger(name=__name__)
from ..attributes import SelectProperty, StringProperty, TextProperty, CurveProperty
from ..memory import MemoryTree
from ..modules import Module
from ..widgets.module_widgets.curve_viewer_widget import CurveViewerWidget
from ..curvedb import CurveDB


def all_curves(instance):
    return CurveDB.all()


class CurveViewer(Module):
    _widget_class = CurveViewerWidget
    """ This Module allows to quickly browse through curves that were taken with pyrpl"""
    _gui_attributes = ["pk", "curve", "params", "save_params"]

    pk = SelectProperty(options=all_curves,
                        doc="the pk of the currently viewed curve",
                        call_setup=True)

    curve = CurveProperty(default=None)

    params = TextProperty()

    def _setup(self):
        self.m = MemoryTree()
        self.curve = self.pk
        if self._curve_object is None:
            self.params = ""
        else:
            self.params = self.m._get_yml(self._curve_object.params)

    def save_params(self):
        self.m = MemoryTree()
        self.m._set_yml(self.params)
        if self._curve_object is not None:
            self._curve_object.params = self.self.m._data
            self._curve_object.save()
