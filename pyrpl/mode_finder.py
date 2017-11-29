import numpy as np
import math

'''
from pyrpl import Pyrpl
cd C:\Users\manip\Documents\GitHub\pyinstruments\users\membranes
import ring_down_module
'''

class PeakFinder(object):
    '''
    def __init__(self):
        pass
    '''
    def find_peaks(self, x, y, width_tolerance=1000, threshold=5, local_zone=1000):
        '''
        Takes a curve (x and y) and finds all peaks withing the given conditions.
        '''
        delta_index = math.ceil(width_tolerance / (x[1] - x[0]))
        delta_local = math.ceil(local_zone / (x[1] - x[0]))
        peaks = []

        for i in range(0, len(x)):
            is_bigger = True  # than ALL local points
            is_smaller = True  # than ALL local points
            if i - delta_local < 0:
                local_data = y[0:i + delta_local]
            if i + delta_local >= len(x) - 1:
                local_data = y[i - delta_local:]
            else:
                local_data = y[i - delta_local:i + delta_local]

            local_mean = np.nanmedian(local_data)
            above_threshold = (y[i] > local_mean + threshold) or (y[i] < local_mean - threshold)

            if i - delta_index < 0:
                for j in range(0, i):
                    is_bigger = (y[i] > y[j]) and is_bigger
                    is_smaller = (y[i] < y[j]) and is_smaller
                for j in range(1, delta_index + 1):
                    is_bigger = (y[i] > y[i + j]) and is_bigger
                    is_smaller = (y[i] < y[i + j]) and is_smaller

            if i + delta_index >= len(x) - 1:
                for j in range(i, len(x)):
                    is_bigger = (y[i] > y[j]) and is_bigger
                    is_smaller = (y[i] < y[j]) and is_smaller
                for j in range(1, delta_index + 1):
                    is_bigger = (y[i] > y[i - j]) and is_bigger
                    is_smaller = (y[i] < y[i - j]) and is_smaller

            else:
                for j in range(1, delta_index + 1):
                    is_bigger = (y[i] > y[i - j]) and (y[i] > y[i + j]) and is_bigger
                    is_smaller = (y[i] < y[i - j]) and (y[i] < y[i + j]) and is_smaller

            is_peak = (is_bigger or is_smaller) and above_threshold
            if is_peak:
                # print(str(x[i]) + ' is bigger ' + str(is_bigger) + ' is_smaller ' + str(is_smaller))
                peaks.append(x[i])
        return peaks


class SAPeakFinder(PeakFinder):
    def __init__(self, pyrpl):
        self.sa = pyrpl.spetrumanalyzer
        self.span = 3.906e6
        self.rbw = 4.117e2

        self.f_start = 1e5
        self.f_end = 1.5e6
        self.threshold = 2 #dB above the median to be considered a peak
        self.size_localdef = 100 #what counts as a peak's "local" surrounding when comparing sizes
        self.median_localdef = 1000 #what counts as a peak's "local" surrounding for the median calculation

        self.sa.setup(span=self.span, rbw=self.rbw, curve_unit='Vpk^2', acbandwidth=0)

        y = self.sa.data_avg[0] #UNRESOLVED HOW TO GET THE RIGHT SIGNAL
        x = self.sa.data_x
        # choosing only selected frequencies
        compare_interval = (x > self.f_start) * (x < self.f_end)
        self.data_y = (10 * np.log10(abs(y) ** 2))[compare_interval]
        self.data_x = x[compare_interval]

        self.peaks = self.find_peaks(self.data_x, self.data_y, width_tolerance=self.size_localdef,
                                     threshold=self.threshold, local_zone=self.median_localdef)


class NAPeakFinder(PeakFinder):
    def __init__(self, pyrpl, sa_peaks):
        self.na = pyrpl.networkanalyzer
        self.delta_f = 1e3 #span of frequency of analyze either side of the found peak
        self.rbw = 1.897e1
        self.avg_per_point = 2
        self.points = 501
        self.amplitude = 1e-2
        self.size_localdef = 100
        self.threshold = 8
        self.median_localdef = 2000  # what counts as a peak's "local" surrounding

        self.peaks = []
        for freq in sa_peaks:
            self.na.setup(start_freq=freq-self.delta_f, stop_freq=freq+self.delta_f, rbw=self.rbw,
                          avg_per_point=self.avg_per_point, points=self.points, amplitude=self.amplitude)
            self.na.single()
            self.data_x = self.na.data_x
            self.data_y = 10*np.log10(abs(self.na.data_avg)**2)

            found_peaks = self.find_peaks(self.data_x, self.data_y, width_tolerance=self.size_localdef,
                                         threshold=self.threshold, local_zone=self.median_localdef)
            self.peaks.append(found_peaks)

class RDMModeFinder(object):
    def __init__(self, pyrpl, na_peaks):
        self.rdm = pyrpl.ringdownmodule
        self.amplitude = 1e-2
        self.points = 1001
        self.rbw = 50
        self.error_tolerance = 10 #tolerance for the optimisation of the ringdown

        for freq in na_peaks:
            self.rdm.setup(frequency=freq, rbw=self.rbw, amplitude=self.amplitude, points=self.points)
            self.rdm.ringdown_now()

            self.rdm.time_fit_start, self.rdm.time_fit_end = self.find_start_and_end_times(self.rdm.data_x,
                                                                                           self.rdm.data_y,
                                                                                           rbw=self.rbw)
            self.rdm.update_fit()
            while abs(self.rdm.delta_f) >= self.error_tolerance:
                self.rdm.optimize()
                self.rdm.time_fit_start, self.rdm.time_fit_end = self.find_start_and_end_times(self.rdm.data_x,
                                                                                               self.rdm.data_y,
                                                                                               rbw=self.rbw)
                self.rdm.update_fit()

    def find_start_and_end_times(self, data_x, data_y, rbw=50):
        '''
        fits the start and end times of a ringdown
        '''
        times = data_x
        y = data_y
        y[y == 0] = [np.nan] * len(np.where(y == 0))  # to prevent having log0
        data_y = 10 * np.log10(abs(y) ** 2)
        average = np.nanmean(data_y)
        time_min = 1.5 / rbw  # empirically decided
        # time_min = 0

        time_constraint = times > time_min
        y_constraint = data_y > average + 15  # empirically decided
        # ensure it discards any True that come after the ringdown is over (oscillating signal)
        for i in range(0, len(y_constraint)):
            if y_constraint[i] == True:
                if False in y_constraint[0:i]:
                    y_constraint[i] == False

        allowed_times = times[time_constraint * y_constraint]
        return allowed_times[0], allowed_times[-1]