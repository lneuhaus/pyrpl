from pyrpl.software_modules.lockbox.signals import *
from pyrpl.software_modules.lockbox.model import *

from pyrpl.software_modules.lockbox.models.fabryperot import *

class FPM(FabryPerot):
    name = "FPM"
    section_name = "fpm"


# add here the custom FPM resonance search functions
