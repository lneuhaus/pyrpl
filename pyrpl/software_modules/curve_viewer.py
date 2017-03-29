import logging
logger = logging.getLogger(name=__name__)
from ..attributes import SelectProperty, StringProperty, TextProperty
from ..memory import MemoryTree
from ..modules import Module
from ..widgets.module_widgets.curve_viewer_widget import CurveViewerWidget
from ..curvedb import CurveDB


def all_curves(instance):
    return CurveDB.all()

class CurveViewer(Module):
    _widget_class = CurveViewerWidget
    """ This Module allows to quickly browse through curves that were taken with pyrpl"""
    _gui_attributes = ["pk", "refresh", "params"]

    pk = SelectProperty(options=all_curves,
                        doc="the pk of the currently viewed curve",
                        call_setup=True)

    params = TextProperty()

    def _setup(self):
        self.curve = CurveDB.get(self.pk)
        self.params = str(self.curve.params)

    def refresh(self):
        self._setup()