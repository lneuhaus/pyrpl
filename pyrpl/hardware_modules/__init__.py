###############################################################################
#    pyrpl - DSP servo controller for quantum optics with the RedPitaya
#    Copyright (C) 2014-2016  Leonhard Neuhaus  (neuhaus@spectro.jussieu.fr)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################

"""All modules are extensively discussed in the Tutorial. Please refer to
there for more information."""

from .ams import AMS
from .arithmetic import Arithmetic, arithmetic_result
from .asg import Asg0, Asg1
from .cordic import Cordic, turns_to_degrees, turns_to_radians
from .dsp import (
    DSP_INPUTS,
    DspModule,
    InputSelectProperty,
    InputSelectRegister,
    all_inputs,
    all_output_directs,
    dsp_addr_base,
)
from .filter import FilterModule
from .hk import HK
from .iir import IIR
from .iq import Iq
from .pid import Pid
from .pwm import Pwm
from .sampler import Sampler
from .scope import Scope
from .trig import Trig
