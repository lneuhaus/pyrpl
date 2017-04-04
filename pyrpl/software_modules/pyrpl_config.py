import logging
logger = logging.getLogger(name=__name__)
from ..attributes import SelectProperty, StringProperty, TextProperty
from ..memory import MemoryTree
from ..modules import Module
from ..widgets.module_widgets.pyrpl_config_widget import PyrplConfigWidget


class PyrplConfig(Module):
    _widget_class = PyrplConfigWidget
    """ This Module allow the Gui to configure the global settins, such as redpitaya and pyrpl """
    _gui_attributes = ["configfile", "module", "refresh", "save", "text"]

    configfile = StringProperty()
    def _init_module(self):
        self.configfile = self.pyrpl.c._filename or ""

    text = TextProperty()

    module = SelectProperty(default="pyrpl",
                            options=lambda inst: ["pyrpl", "redpitaya"] +
                                                 [m.name for m in inst.pyrpl.software_modules] ,
                            doc="this selector allows to choose which module is configured",
                            call_setup=True)

    def get_current_branch(self):
        if (self.configfile == self.pyrpl.c._filename) \
                or (self.configfile == "" and self.pyrpl.c._filename is None):
            self.config = self.pyrpl.c
        else:
            self.config = MemoryTree(self.configfile)
        return self.config._get_or_create(self.module)

    def _setup(self):
        self.text = self.get_current_branch()._get_yml()

    def save(self):
        self.get_current_branch()._set_yml(self.text)
        try:
            module = getattr(self.pyrpl, self.module)
        except AttributeError:
            pass
        else:
            module._load_setup_attributes()

    def refresh(self):
        self._setup()