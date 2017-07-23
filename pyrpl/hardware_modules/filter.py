from .dsp import DspModule
from ..attributes import FilterRegister


class FilterModule(DspModule):
    inputfilter = FilterRegister(0x120,
                                 filterstages=0x220,
                                 shiftbits=0x224,
                                 minbw=0x228,
                                 doc="Input filter bandwidths [Hz]. "
                                     "0 = off, "
                                     "positive bandwidth <=> lowpass, "
                                     "negative bandwidth <=> highpass. ")

    @property
    def inputfilter_options(self):
        return self.__class__.inputfilter.valid_frequencies(self)

    #_valid_inputfilter_frequencies = inputfilter.valid_frequencies