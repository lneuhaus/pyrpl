import pandas
import scipy.optimize
import numpy
import numpy as np
import collections
import math
from guiqwt.widgets.fit import FitParam, guifit
import scipy.signal
import scipy.special
import logging

class Fit(object):
    def __init__(self, data, func, fixed_params={}, manualguess_params={},
                 maxiter=10000, errfn='error_vector', autofit=True,
                 graphicalfit=False):
        self.logger = logging.getLogger(__name__)
        self._x_npy = None
        self._y_npy = None
        self.autofit = autofit
        self.autofitgraphical = graphicalfit
        self.data = pandas.Series(np.array(data.values, dtype=np.double),
                    index = np.array(data.index.values, dtype=np.double))
        self.sqerror = float('nan')
        self.stepcount = 0
        self.maxiter = maxiter
        self.commentstring = ''
        self.pre_fixed_params = collections.OrderedDict(fixed_params)
        self.fixed_params = collections.OrderedDict()
        self.manualguess_params = collections.OrderedDict(manualguess_params)
        self.diag = None

        # the fit function is passed as an argument
        self.fn = func
        
        # define the error function to be optimised
        self.errfn = errfn
        self.fn_error = self.__getattribute__(self.errfn)

        # may be implemented in the future
        self.autoguess_params = collections.OrderedDict()

        # take all parameters passed during the function call as fixed,
        # and assume that others have to be guessed
        # fixed_params are invariably fixed
        # manualguess_params have been guessed manually
        # the remaining autoguess_params were guessed by the guess function
        self.fit_params = collections.OrderedDict()
        self.fit_params_errors = collections.OrderedDict()
        
        for key in self.fn.func_code.co_varnames[0:self.fn.func_code.co_argcount]:
            if key in self.pre_fixed_params:
                self.fixed_params[key] = self.pre_fixed_params[key]
            elif key in self.manualguess_params:
                self.fit_params[key] = self.manualguess_params[key]
            else: 
                self.fit_params[key] = self.autoguess_params[key]
                # this will throw an error...

        self.logger.debug("Square sum of data: " + str((self.data**2).sum()))
        self.logger.debug("Calling fit function with following guesses: ")
        self.logger.debug(str(dict(self.getparams())))
        
        if self.autofit:
        # the parameters in fixed_params and fit_params are now ready for the fit
            if not self.autofitgraphical:
                res = self.fit()
                self.logger.debug("Return of fit optimisation function: ")
                self.logger.debug(str(res))
            else:
                res = self.graphicalfit()
                self.logger.debug("Return of fit optimisation function: ")
                self.logger.debug(str(res))

                    
    def error_vector(self, args):
        "returns a vector containing the difference between fit and data - not the square of it!"
        # unfold the list of parameters back into the dictionary 
        for index, key in enumerate(self.fit_params):
            self.fit_params[key] = float(args[index])
        # calculate the square error
        self.sqerror_vector = self.fn(**self.getparams())-self.data.values
        if isinstance(self.sqerror_vector[0], np.complex):
            self.sqerror_vector = np.abs(self.sqerror_vector)
        return np.array(self.sqerror_vector, dtype=np.float)

    def log_error_vector(self, args):
        "returns a vector containing the difference between log(fit) and log(data) - not the square of it!"
        # unfold the list of parameters back into the dictionary 
        for index, key in enumerate(self.fit_params):
            self.fit_params[key] = float(args[index])
        
        # calculate the square error
        self.sqerror_vector = np.log(self.fn(**self.getparams()))-np.log(self.data.values)
        if isinstance(self.sqerror_vector[0], np.complex):
            self.sqerror_vector = np.abs(self.sqerror_vector)
        return np.array(self.sqerror_vector, dtype=np.float)

    def getparams(self):
        params = self.fit_params.copy()
        params.update(self.fixed_params)
        return params

    def x(self):
        if self._x_npy is None:
            self._x_npy = numpy.array(self.data.index.values, dtype=np.double)
        return self._x_npy
    
    def y(self):
        if self._y_npy is None:
            if self.data.values.dtype == complex:
                self._y_npy = numpy.array(self.data.values,dtype=complex)
            else:
                self._y_npy = numpy.array(self.data.values,dtype=np.double)
        return self._y_npy

    def getsqerror(self):
        """ rms of fit residue"""
        sq = np.mean(np.abs((self.fn(**self.getparams())-self.data))**2)
        return np.sqrt(sq)

    def fit(self):
        res = scipy.optimize.leastsq(func=self.fn_error,
                                     x0=self.fit_params.values(),
                                     xtol=1e-15,
                                     ftol=1e-15,
                                     gtol=0.0,
                                     maxfev=self.maxiter,
                                     diag=self.diag,
                                     full_output=True,
                                     epsfcn=0.0 
                                     )
        self.sqerror = self.getsqerror()
        self.logger.debug("Fit completed with sqerror = " + str(self.sqerror))
        self.logger.debug("Obtained parameter values: ")
        self.logger.debug(dict(self.getparams()))
        # evaluate the performed fit in fitdata
        self.fitdata = pandas.Series(data=self.fn(**self.getparams()), index=self.x())
        #estimation of fit error
        self.logger.debug('%s', res)
        (popt, pcov, infodict, errmsg, ier) = res
        self.fit_params_errors = collections.OrderedDict()
        if pcov is None:
            return res
        errors = np.sqrt(np.diag(pcov*self.sqerror))
        if len(errors)==len(self.fit_params):
            for index, key in enumerate(self.fit_params):
                self.fit_params_errors[key+"_error"] = float(errors[index])
        return res

    def graphicalfit(self):
        # SHOW = True # Show test in GUI-based test launcher
        x = self.x()
        y = self.y()
        if (y.dtype == np.dtype('complex128') or y.dtype == np.dtype(
                'complex') or np.abs(np.imag(y[0])) > 0):
            self.logger.warning("Complex data!!! loosing phase information in " \
                          "graphical fit")
            iscomplex = True
            y = np.abs(y)

        def fitfn(x, params):
            # ignore the x
            for index, key in enumerate(self.fit_params):
                self.fit_params[key] = float(params[index])
                res = self.fn(**self.getparams())
                if len(x) != len(self.x()):
                    s = pandas.Series(res, index=self.x())
                    res = s.loc[x].values
            if res.dtype == np.dtype('complex128'):
                res = np.abs(res)
            return res

        self.graphical_params = list()
        for index, key in enumerate(self.fit_params):
            fpin = self.fit_params[key]
            if fpin == 0:
                fpmin = -1e-6
                fpmax = 1e-6
            else:
                fpmin = fpin / 100.
                fpmax = fpin * 10.
            fp = FitParam(key, fpin, fpmin, fpmax, logscale=False, steps=2000,
                          format='%.8f')
            self.graphical_params.append(fp)
        values = guifit(x, y, fitfn, self.graphical_params, xlabel="x-axis",
                        ylabel="y-axis")
        if values is None:
            self.gfit_concluded = False
        else:
            self.gfit_concluded = True

        self.logger.debug("Graphical fit finished with the following values: ")
        self.logger.debug(values)
        self.logger.debug([param.value for param in self.graphical_params])
        self.sqerror = self.getsqerror()
        self.logger.debug("Fit completed with sqerror = " + str(self.sqerror))
        self.logger.debug("Obtained parameter values: ")
        self.logger.debug(dict(self.getparams()))
        # evaluate the performed fit in fitdata
        self.fitdata = pandas.Series(data=self.fn(**self.getparams()),
                                     index=self.x(), \
                                     name='fitfunction: ' + self.func)
        return values
