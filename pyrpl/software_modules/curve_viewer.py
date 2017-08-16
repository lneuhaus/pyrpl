import logging
logger = logging.getLogger(name=__name__)
from ..attributes import SelectProperty, StringProperty, TextProperty, \
    CurveProperty, CurveSelectProperty, CurveSelectListProperty
from ..memory import MemoryTree
from ..modules import Module
from ..widgets.module_widgets.curve_viewer_widget import CurveViewerWidget
from ..curvedb import CurveDB


MAX_CURVES = 100  # maximum number of curves to display


def all_curves(instance=None):
    return CurveDB.all()[:MAX_CURVES]


class CurveViewer(Module):
    """
    This Module allows to browse through curves that were taken with pyrpl
    """
    _widget_class = CurveViewerWidget
    _gui_attributes = ["curve_name", "pk", "curve", "params", "save_params",
                       "delete_curve", "refresh_curve_list"]
    pk = CurveSelectListProperty(doc="the pk of the currently viewed curve",
                                 call_setup=True)
    curve = CurveProperty(default=None, show_childs=True)
    params = TextProperty()
    curve_name = StringProperty(doc="Name of the currently viewed curve")
                                # read_only=True)  # TODO: implement read-only

    def _setup(self):
        self.m = MemoryTree()
        self.curve = self.pk
        if self._curve_object is None:
            self.params = ""
            self.curve_name = ""
        else:
            self.params = self.m._get_yml(self._curve_object.params)
            self.curve_name = self._curve_object.params['name']

    def save_params(self):
        self.m = MemoryTree()
        self.m._set_yml(self.params)
        if self._curve_object is not None:
            self._curve_object.params = self.self.m._data
            self._curve_object.save()

    def delete_curve(self):
        if self._curve_object is not None:
            self._logger.info("Curve with id %s will be deleted!",
                              self._curve_object.pk)
            del_pk = self._curve_object.pk
            del_index = self.pk_options.index(del_pk)
            self._curve_object.delete()
            new_options = list(self.__class__.pk.options(self).keys())
            new_index = max(0, min(del_index, len(new_options)-2)) # try to select the same list item as before
            new_option = new_options[new_index]
            if new_option != del_pk:
                self.pk = new_option

    def refresh_curve_list(self):
        self.__class__.pk.options(self)
