import collections
from scipy.optimize import leastsq
import json
import time
import matplotlib.pyplot as plt
from collections import OrderedDict
import numpy as np
import os
import logging
import pandas
from . import CurveDB
from . import iir
from .sound import sine


def iirparams_from_curve(id):
    c = CurveDB.get(id)
    return iirparams_from_curveparams(c.params)


def iirparams_from_curveparams(curveparams):
    params = dict()
    for e in ['loops', 'gain', 'inputfilter']: #'invert', :
        if e in curveparams:
            params[e] = curveparams[e]
    if "pole_real" in curveparams:
        params['poles'] = list(np.array(json.loads(curveparams["pole_real"]),
                                        dtype=np.complex128) +
                               1j * np.array(json.loads(curveparams["pole_imag"]),
                                             dtype=np.complex128))
    else:
        params['poles'] = list()
    if "zero_real" in curveparams:
        params['zeros'] = list(np.array(json.loads(curveparams["zero_real"]),
                                        dtype=np.complex128) +
                               1j * np.array(json.loads(curveparams["zero_imag"]),
                                             dtype=np.complex128))
    else:
        params['zeros'] = list()
    return params


class BodePlot(object):
    """ Class that generates bodeplots from an OrderedDict of data +
    style specification

    Parameters
        ----------
        data: collections.OrderedDict
            An ordered dict containing key-value pairs of datalabels and data.
            The data can be either pandas.Series objects or tuples of x and
            y arrays. y should be complex to benefit from the bodeplot
            functionality.
        datastyle: dict
            a dictionary whose keys are the same as in data, containing the
            plot style parameter for the trace
        autoplot: bool
            Plot automatically upon startup
        xlog: bool
            Makes x-axis logscaled.
        """

    def __init__(self, data, datastyle={'data': 'b-'},
                 autoplot=True, xlog=True, legend=True):
        self._logger = logging.getLogger(__name__)
        if isinstance(data, int):
            self.data = OrderedDict({'data': CurveDB.get(data).data})
        else:
            self.data = OrderedDict({'data': data})
        self.xlog = xlog
        self.autoplot = autoplot
        self.datastyle = datastyle
        self.legend = legend
        self.plottedlines = {}
        self.info = ''
        if autoplot:
            self.plot()

    @property
    def x(self):
        return np.asarray(self.data['data'].index.values, dtype=np.float)

    def plot(self, unwrap=False, newfigstyle='y-', label=""):
        # make a bode plot of the signal
        show = False
        if not hasattr(self, 'fig'):
            plt.close()
            show = True
            fig, axarr = plt.subplots(2, sharex=True)
            self.fig = fig
            axarr[0].set_ylabel('Amplitude [dB]', color='b')
            axarr[0].grid(True)
            axarr[1].set_xlabel('Frequency [Hz]')
            axarr[1].set_ylabel('Phase (degrees)', color='b')
            axarr[1].grid(True)
            self.axarr = axarr
            if self.xlog:
                self.axarr[0].set_xscale('log')
                self.axarr[1].set_xscale('log')
        else:
            fig = self.fig
            axarr = self.axarr
        plotted = {}
        for i, (label, v) in enumerate(self.data.items()):
            data = v
            try:
                style = self.datastyle[label]
            except KeyError:
                style = 'k-'
            if isinstance(data, pandas.Series):
                x = data.index.values
                y = data.values
            elif isinstance(data, (np.ndarray, np.generic)):
                x, y = self.x, data
            else:
                x, y = data
            if unwrap:
                angles = 180. / np.pi * np.unwrap(np.angle(y))
            else:
                angles = 180. / np.pi * np.angle(y)
            try:
                index = self.plottedlines[label]
            except KeyError:
                mag = self.axarr[0].plot(x, 20 * np.log10(np.abs(y)), style)
                plt.setp(mag, antialiased=True, label=label)
                phase = self.axarr[1].plot(x, angles, style)
                index = i
            else:
                l_mag = self.fig.axes[0].lines[index]
                l_phase = self.fig.axes[1].lines[index]
                l_mag.set_data(x, 20 * np.log10(np.abs(y)))
                l_phase.set_data(x, angles)
            plotted[label] = index
            if label.startswith('poles') or label.startswith('zeros'):
                self.fig.axes[0].lines[index].set_markersize(10)
                self.fig.axes[1].lines[index].set_markersize(10)
                self.fig.axes[0].lines[index].set_markeredgewidth(3)
                self.fig.axes[1].lines[index].set_markeredgewidth(3)
        self.plottedlines = dict(plotted)
        if self.legend:
            leg = self.axarr[0].legend(loc='best', framealpha=0.5)
            leg.draggable(state=True)
        plt.title(self.info)
        plt.plot()
        if show:
            self.axarr[0].axis('tight')
            self.axarr[1].axis('tight')
            plt.show()


class BodeFit(BodePlot):
    # all the properties that are saved with a fit (poles and zeros as well)
    extraparams = ['loops', 'gain', 'invert', 'delta', 'actpole', 'actzero',
                   'inputfilter']

    def __init__(self, id=None, xlog=True, invert=True,
                 autogain=True, legend=True, showstability=False):
        if id is not None:
            # id may only be None when the class is re-initialized so it
            # keeps its curve object
            self.c = CurveDB.get(id)
        self.default(autogain=autogain)
        self.invert = invert
        self.showstability = showstability
        super(BodeFit, self).__init__(self.c.data, autoplot=False,
                                      xlog=xlog, legend=legend)
        self.refresh()

    def default(self, autogain=True):
        self._poles = []
        self._zeros = []
        self._gain = 1.0
        self.actzero = None
        self.actpole = None
        self.delta = 100
        self.loops = None
        if autogain:
            g0 = self.c.data.loc[:1000.0].mean()
            if np.isnan(g0):
                g0 = self.c.data.iloc[:10].mean()
            self._gain = abs(g0)
            a = np.angle(g0, deg=True)
            if a > 90 and a <= 270:
                self._gain *= -1

    def update_data(self):
        self.data['data'], self.datastyle['data'] = self.c.data, 'b-'
        self.data['fit'], self.datastyle['fit'] = \
            self.transfer_function(), 'r-'
        if self.invert:
            dataxfit = self.data['data'] / self.data['fit']
        else:
            dataxfit = self.data['data'] * self.data['fit']
        self.data['data x fit'], self.datastyle['data x fit'] = dataxfit, 'g-'

        self.datastyle.update({'poles': 'kx',
                               'zeros': 'ko',
                               'poles (active)': 'rx',
                               'zeros (active)': 'ro'})
        if self.poles:
            self.data['poles'] = self.getpz(self.poles)
        else:
            self.data['poles'] = pandas.Series()
        if self.zeros:
            self.data['zeros'] = self.getpz(self.zeros)
        else:
            self.data['zeros'] = pandas.Series()
        if self.actpole is not None and self.poles:
            self.data['poles (active)'] = self.getpz([self.poles[self.actpole]])
        else:
            self.data['poles (active)'] = pandas.Series()
        if self.actzero is not None and self.zeros:
            self.data['zeros (active)'] = self.getpz([self.zeros[self.actzero]])
        else:
            self.data['zeros (active)'] = pandas.Series()
        if self.showstability:
            punstable = dataxfit[np.angle(dataxfit, deg=True) > 0.0]
            gunstable = punstable[punstable.abs()>1.0]
            self.data['phase unstable'] = punstable
            self.datastyle['phase unstable'] = 'm.'
            self.data['phase and gain unstable'] = gunstable
            self.datastyle['phase and gain unstable'] = 'y.'

    def update_info(self, append=''):
        string = ""
        if self.actzero is not None:
            string += "Active zero: "
            string += str(self.zeros[self.actzero]) + ", "
        if self.actpole is not None:
            string += "Active pole: "
            string += str(self.poles[self.actpole]) + ", "
        string += "gain=" + str(self.gain) + ", "
        string += "step=" + str(self.delta) + ", "
        string += "" + str(len(self.poles)) + " poles, "
        string += str(len(self.zeros)) + " zeros, "
        string += append
        plt.title(string)
        self.info = string

    def refresh(self):
        self.update_data()
        self.update_info()
        self.plot()

    def getpz(self, pointlist):
        """ gets 'data' of poles or zeros for plotting """
        freqs = list()
        for p in pointlist:
            if np.imag(p) == 0:
                freqs.append(np.abs(p))
            else:
                freqs.append(np.abs(np.imag(p)))
        freqs = np.array(freqs)
        return self.transfer_function(freqs)

    @property
    def poles(self):
        """ this list only contains single poles/zeros. Complex conjugates
        are automatically added"""
        return self._poles

    @property
    def zeros(self):
        """ this list only contains single poles/zeros. Complex conjugates
        are automatically added"""
        return self._zeros

    @property
    def gain(self):
        return self._gain

    @gain.setter
    def gain(self, v):
        self._gain = v

    @property
    def inputfilter(self):
        if not hasattr(self, '_inputfilter'):
            self._inputfilter = 0
        return self._inputfilter

    @inputfilter.setter
    def inputfilter(self, v):
        self._inputfilter = v

    def transfer_function(self, frequencies=None):
        if frequencies is None:
            frequencies = self.x
        self.iirfilter = iir.IirFilter(self.zeros,
                                       self.poles,
                                       self.gain,
                                       loops=self.loops,
                                       frequencies=frequencies,
                                       inputfilter=self.inputfilter
                                       )
        y = self.iirfilter.tf_continuous()
        return pandas.Series(y, index=frequencies)

    def loadfit(self, id=None):
        if not id is None:
            c = CurveDB.objects.get(pk=id)
        else:
            try:
                c = self.c.childs.filter_param('name', value="iir fit").latest()
            except:
                return
        self.params = c.params
        self.refresh()

    def savefit(self):
        self.refresh()
        c = CurveDB.create(self.data['fit'])
        c.name = "iir fit"
        c.save()
        self.c.add_child(c)
        c.params.update(self.params)
        c.save()
        return c

    @property
    def params(self):
        pd = dict()
        pd["pole_real"] = json.dumps(list(np.real(self.poles)))
        pd["pole_imag"] = json.dumps(list(np.imag(self.poles)))
        pd["zero_real"] = json.dumps(list(np.real(self.zeros)))
        pd["zero_imag"] = json.dumps(list(np.imag(self.zeros)))
        for e in self.extraparams:
            p = self.__getattribute__(e)
            if isinstance(p, list):
                p = p[0]
            pd[e] = p
        return pd

    @params.setter
    def params(self, v):
        for e in self.extraparams:
            if e in v:
                self.__setattr__(e, v[e])
        if "pole_real" in v:
            self._poles = list(np.array(json.loads(v["pole_real"]),
                                       dtype=np.complex128) + 1j * np.array(
                json.loads(v["pole_imag"]), dtype=np.complex128))
        else:
            self._poles = list()
        if "zero_real" in v:
            self._zeros = list(np.array(json.loads(v["zero_real"]),
                                        dtype=np.complex128) + 1j * np.array(
                json.loads(v["zero_imag"]), dtype=np.complex128))
        else:
            self._zeros = list()

    def savefig(self, filename="bodeplot", DPI=600, outdir=None):
        if outdir is None:
            self.outdir = self.c.get_or_create_dir()
        else:
            self.outdir = outdir
        plt.savefig(os.path.join(self.outdir, filename + '.png'), dpi=DPI,
                    bbox_inches="tight")


class BodeFitIIR(BodeFit):
    def update_data(self):
        super(BodeFitIIR, self).update_data()
        self.datastyle['discrete'] = 'y-'
        self.datastyle['coefficients'] = 'c-'
        self.datastyle['rounded'] = 'm-'
        self.datastyle['rounded+delay+inputfilter'] = 'k-'
        # self.iirfilter has been updated by BodeFitIIR.update_data
        iirfilter = self.iirfilter
        #self.data['discrete'] = iirfilter.tf_discrete(self.x)
        self.data['coefficients'] = iirfilter.tf_coefficients(self.x)
        #self.data['rounded'] = iirfilter.tf_rounded(self.x)
        self.data['final'] = iirfilter.tf_final(self.x)

    def update_info(self, append=''):
        info = 'loops='+str(self.iirfilter.loops)+', '+append
        return super(BodeFitIIR, self).update_info(append=info)


class BodeFitIIRGui(BodeFitIIR):
    def __init__(self, id=None, xlog=True, invert=True, autogain=True,
                 legend=False, showstability=False):
        super(BodeFitIIRGui, self).__init__(id=id, xlog=xlog, invert=invert,
                                         autogain=autogain, legend=legend,
                                         showstability=showstability)
        self._tlast = 0
        self.loadfit()
        self.lockbox = None
        self.pid = None
        self.clickmode()

    def clickmode(self):
        self.cid1 = self.fig.canvas.mpl_connect('button_press_event',
                                                self.onclick)
        self.cid2 = self.fig.canvas.mpl_connect('key_press_event',
                                                self.onkeypress)

    def _getclosestindex(self, liste, value):
        print "Searching closest pole/zero to frequency", value, "in", len(
            liste), "-element list"
        ibest = -1
        dbest = 99999999999999
        for i in range(len(liste)):
            print i
            if np.imag(liste[i]) == 0:
                d = np.abs(value - np.abs(liste[i]))
            else:
                d = np.abs(value - np.abs(np.imag(liste[i])))
            if d < dbest:
                dbest = d
                ibest = i
        return ibest

    def onclick(self, event):
        if time.time()-self._tlast < 0.1 and event == self._evlast:
            return
        self._tlast = time.time()
        self._evlast = event
        print "clicked with key",event.key
        self.event = event
        x = event.xdata
        y = event.ydata
        if event.key == "control":
            if event.button == 1:
                print "adding double pole"
                self.poles.append(-1j*x-1.0000001)
                self.actpole = -1
                self.actzero = None
            elif event.button == 3:
                print "adding double zero"
                self.zeros.append(-1j*x-1.0000001)
                self.actpole = None
                self.actzero = -1
        if event.key == "ctrl+shift":
            if event.button == 1:
                print "adding signle pole"
                self.poles.append(-x)
                self.actpole = -1
                self.actzero = None
            elif event.button == 3:
                print "adding single zero"
                self.zeros.append(-x)
                self.actpole = None
                self.actzero = -1
        if event.key == "alt":
            if event.button == 1:
                self.actpole = self._getclosestindex(self.poles, x)
                self.actzero = None
                print "shifting pole: "
                print self.poles[self.actpole]
            if event.button == 3:
                self.actpole = None
                self.actzero = self._getclosestindex(self.zeros, x)
                print "shifting zero: "
                print self.zeros[self.actzero]
        self.refresh()
        
    def onkeypress(self, event):
        if time.time()-self._tlast < 0.1 and event == self._evlast:
            return
        self._tlast = time.time()
        self._evlast = event
        if not hasattr(event, "key"):
            class ev(object):
                key = event
            event = ev()
        self.event = event
        print event.key
        delta = 0
        if event.key == "alt+up":
            delta = 1
        elif event.key == 'alt+down':
            delta = -1
        elif event.key == 'alt+right':
            delta = 1j
        elif event.key == 'alt+left':
            delta = -1j
        elif event.key == 'ctrl+up':
            self.delta *= 2.0
            self.refresh()
            return
        elif event.key == 'ctrl+down':
            self.delta /= 2.0
            self.refresh()
            return
        elif event.key == 'ctrl+alt+up':
            self.gain *= 2.0
            self.refresh()
            return
        elif event.key == 'ctrl+alt+down':
            self.gain /= 2.0
            self.refresh()
            return
        elif event.key == 'i':
            self.gain *= -1.0
            self.refresh()
            return
        elif event.key == 'f6':
            self.savefit()
            sine(2000, 0.2)
            return
        elif event.key == 'f9':
            self.default()
            sine(5000, 0.1)
            return
        elif event.key == 'd':
            if self.actpole is not None:
                self.poles.pop(self.actpole)
                if self.poles:
                    self.actpole = -1
                else:
                    self.actpole = None
            if self.actzero is not None:
                self.zeros.pop(self.actzero)
                if self.zeros:
                    self.actzero = -1
                else:
                    self.actzero = None
            self.refresh()
            return
        else:
            self.otherkeyactions(event.key)
            return
        realdelta = np.complex(self.delta) * np.complex(delta)
        print ("delta: "+str(realdelta))
        if self.actpole is not None:
            ipole = self.actpole
            if np.imag(self.poles[ipole]) < 0:
                self._poles[ipole] += np.conjugate(realdelta)
            else:
                self._poles[ipole] += realdelta
        if self.actzero is not None:
            izero = self.actzero
            if np.imag(self.zeros[izero]) < 0:
                self._zeros[izero] += np.conjugate(realdelta)
            else:
                self._zeros[izero] += realdelta
        self.refresh()

    def otherkeyactions(self, key):
        print("No action defined for key %s"%key)
        pass


class BodeFitIIRGuiOptimisation(BodeFitIIRGui):
    """ Numerical p-norm calculation of filter coefficients """
    def __init__(self, id=None, xlog=True, invert=False, autogain=True,
                 legend=True, showstability=False):
        super(BodeFitIIRGuiOptimisation, self).__init__(id=id, xlog=xlog,
                                     invert=invert,
                                     autogain=autogain, legend=legend,
                                     showstability=showstability)
        self._tlast = 0
        self.loadfit()
        self.lockbox = None
        self.pid = None
        self.datastyle['target'] = 'yx'
        self.data['target'] = pandas.Series()
        self.setdefaulttarget()
        self.p = 2  # p-norm is of the logarithmic error used to compute error
        self.refresh()

    @property
    def target(self):
        return self.data['target']

    @target.setter
    def target(self, v):
        self.data['target'] = v

    def error(self):
        f = self.target.index.values
        err = np.abs(np.log(self.target.values-self.iirfilter.tf_filtered(f)))**self.p
        return err

    def otherkeyaction(self, key):
        if key == 'f2':
            print (key + 'trying to fit...')

    def setdefaulttarget(self):
        fs = [6010., 11955., 22351., 41504., 56795., 112359.]
        amps = [64, 64, 2, 32, 32, 20]
        phases = [55, 63, 120, 102, -25, 105]
        t = np.array(amps, dtype=np.complex) * np.exp(1j * np.array(
            phases) * np.pi / 180.0)
        self.target = pandas.Series(t, index=fs)
        return self.target

    def minimize(self, coefficients=None, degree=None, initialize=False):
        if initialize:
            if coefficients is not None:
                degree = len(coefficients)
            else:
                # try a random set of coefficients
                if degree is None:
                    degree = np.len(self.target)
                coeff = np.zeros((degree, 6), dtype=np.float64)
                coeff[0, 0] = kc
                coeff[:, 3] = 1.0
                return coeff
        # actual optimisation
        self.earliercoefficients = np.array(self.coefficients)
        def error(*args):
            pass

    @property
    def coefficients(self):
        if not hasattr(self, '_coefficients'):
            self._coefficients = self.unitycoefficients()
        return self._coefficients

    @coefficients.setter
    def coefficients(self, v):
        self.iirfilter._coefficients = v
        self.data['discrete'] = self.iirfilter.tf_discrete()
        self.datastyle['discrete'] = 'm-'

    @property
    def loops(self):
        if hasattr(self, '_loops'):
            return self._loops
        else:
            return self._defaultloops

    @loops.setter
    def loops(self, v):
        self._loops = v

    def unitycoefficients(self, degree=1, k=1):
        coeff = np.zeros((degree, 6), dtype=np.float64)
        coeff[0, 0] = k
        coeff[:, 3] = 1.0
        return coeff

    def setcoefficients(self, num0s, num1s, den0s, den1s):
        self.coefficients = np.zeros((len(num0s), 6), dtype=np.float64)
        self.coefficients[:, 0] = num0s
        self.coefficients[:, 1] = num1s
        self.coefficients[:, 2] = 0
        self.coefficients[:, 3] = 1
        self.coefficients[:, 4] = den0s
        self.coefficients[:, 5] = den1s
        return self.coefficients

    def randomcoefficients(self, degree=10, scale=4.0):
        self.setcoefficients(
            np.random.normal(scale=scale, size=degree),
            np.random.normal(scale=scale, size=degree),
            np.random.normal(scale=scale, size=degree),
            np.random.normal(scale=scale, size=degree))
        return self.coefficients

    def nosorandomcoefficients(self, degree=10, scale=4.0):
        self.setcoefficients(
            np.random.normal(scale=scale, size=degree),
            np.random.normal(scale=scale, size=degree),
            np.random.normal(scale=scale, size=degree),
            np.random.normal(scale=scale, size=degree))
        return self.coefficients

    @property
    def sampling_time(self):
        return 8e-9 * self.loops

    _defaultloops = 16

    def otherkeyactions(self, key):
        self._logger.debug("Otherkeyactions reached")
        if key == 'f7':  # na measurement
            print ('Measuring IIR filter response...')
            rp = self.redpitaya
            if rp is not None:
                # save previous state
                iir = rp.iir
                iir.on = False
                iirinputfilter = iir.inputfilter
                iircoeff = iir.coefficients
                iirod = iir.output_direct
                iirinput = iir.input
                naod = rp.na.iq.output_direct
                nainput = rp.na.iq.input
                # set measurement state - na must be in the right setting (gui)
                iir.output_direct = 'off'
                iir.input = rp.na.iq
                rp.na.iq.output_direct = 'off'
                rp.na.input = 'iir'
                iir.setup(self.zeros, self.poles, self.gain,
                          loops=self.loops,
                          inputfilter=self.inputfilter)
                sine(1000, 0.1)
                f, tf, _ = rp.na.curve()
                # restore previous state
                iir.on = False
                self.data['measurement'] = pandas.Series(tf, index=f)
                self.datastyle['measurement'] = 'r.'
                iir.coefficients = iircoeff
                iir.inputfilter = iirinputfilter
                iir.output_direct = iirod
                iir.input = iirinput
                rp.na.iq.output_direct = naod
                rp.na.input = nainput
                iir.on = True
                self.refresh()
                return
        elif key == 'f5':
            print ('Updating IIR filter...')
            rp = self.redpitaya
            if rp is not None:
                rp.iir.setup(zeros=self.zeros,
                               poles=self.poles,
                               gain=self.gain,
                               inputfilter=self.inputfilter,
                               loops=self.loops)
                sine(1000, 0.1)
                self.refresh()
                return
        elif key == 'f12':
            print ('Setting up NA to default values..')
            rp = self.redpitaya
            if rp is not None:
                p = self.c.params
                setupparams = ['start', 'stop', 'amplitude', 'points', 'rbw',
                               'input', 'output_direct', 'avg']
                setupdict = {k: p[k] for k in setupparams}
                rp.na.setup(**setupdict)
                sine(1000, 0.1)
                self.refresh()
                return
        elif key == 'ctrl+alt+left':
            self.loops -= 1
            self.refresh()
            return
        elif key == 'ctrl+alt+right':
            self.loops += 1
            self.refresh()
            return

    @property
    def redpitaya(self):
        from .redpitaya import RedPitaya
        if hasattr(self, '_redpitaya'):
            return self._redpitaya
        elif hasattr(self, 'lockbox'):
            if isinstance(self.lockbox, RedPitaya):
                return self.lockbox
            elif hasattr(self.lockbox, 'rp'):
                return self.lockbox.rp
        else:
            return None
