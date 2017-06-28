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


# Dummy version of CurveDB class
#
# The original version of this code uses a package called pyinstruments, which
# is a database for experimental measurement data.
# This class simulates the functionality of pyinstruments to guarantee
# standalone functionality of the rplockbox package.
# In case you
# For full performance, download pyinstruments to replace this class
# otherwise you can custimize here what is to be done to your data
#
import numpy as np
import pandas
import pickle
import os
import logging


# optional override of CurveDB class with custom module, as defined in
# ./pyrpl/config/global_config.yml
try:
    from . import global_config
    CurveDB = __import__(global_config.general.curvedb).CurveDB
except:
    from . import user_curve_dir
    class CurveDB(object):
        _dirname = user_curve_dir
        if not os.path.exists(_dirname): # if _dirname doesn't exist, some unexpected errors will occur.
            os.mkdir(_dirname)

        def __init__(self, name="some_curve"):
            """
            A CurveDB object has
            - name   = string to give the curve a name
            - pk     = integer to uniquely identify the curve (the database primary key)
            - data   = pandas.Series() object to hold any data
            - params = dict() with all kinds of parameters
            """
            self.logger = logging.getLogger(name=__name__)
            self.params = dict()
            self.data = pandas.Series()
            self.name = name

        @property
        def name(self):
            return self.params["name"]

        @name.setter
        def name(self, val):
            self.params["name"] = val
            return val

        @classmethod
        def create(cls, *args, **kwds):
            """
            Creates a new curve, first arguments should be either
            Series(y, index=x) or x, y.
            kwds will be passed to self.params
            """
            if len(args) == 1:
                if isinstance(args[0], pandas.Series):
                    ser = args[0]
                else:
                    y = np.array(args[0])
                    ser = pandas.Series(y)
            elif len(args) == 2:
                x = np.array(args[0])
                y = np.array(args[1])
                ser = pandas.Series(y, index=x)
            else:
                raise ValueError("first arguments should be either x or x, y")
            obj = cls()
            obj.data = ser

            obj.params = kwds
            if not 'name' in obj.params:
                obj.params['name'] = 'new_curve'
            pk = obj.pk  # make a pk
            if "childs" not in obj.params:
                obj.params["childs"] = None
            if ("autosave" not in kwds) or (kwds["autosave"]):
                obj.save()
            return obj

        def plot(self):
            self.data.plot()

        # Implement the following methods if you want to save curves permanently
        @classmethod
        def get(cls, curve):
            if isinstance(curve, CurveDB):
                return curve
            elif isinstance(curve, list):
                return [CurveDB.get(c) for c in curve]
            else:
                with open(os.path.join(CurveDB._dirname, str(curve) + '.p'), 'rb') as f:
                    # rb is for compatibility with python 3
                    # see http://stackoverflow.com/questions/5512811/builtins-typeerror-must-be-str-not-bytes
                    curve = CurveDB()
                    curve._pk, curve.data, curve.params = pickle.load(f)
                return curve

        def save(self):
            with open(os.path.join(self._dirname, str(self.pk) + '.p'), 'wb') as f:
                # wb is for compatibility with python 3
                # see http://stackoverflow.com/questions/5512811/builtins-typeerror-must-be-str-not-bytes
                pickle.dump((self.pk, self.data, self.params), f)

        def delete(self):
            # remove the file
            delpk = self.pk
            parent = self.parent
            try:
                filename = os.path.join(self._dirname, str(self.pk) + '.p')
                os.remove(filename)
            except OSError:
                self.logger.warning("Could not find remove the file %s. ",
                                    filename)
            # remove dependencies.. do this at last so the curve is deleted if an
            # error occurs (i know..). The alternative would be to iterate over all
            # curves to find dependencies which could be slow without database.
            # Heavy users should really use pyinstruments.
            self.logger.warning("Make sure curve %s was not parent of another " +
                                "curve.")
            if parent:
                parentchilds = parent.childs
                parentchilds.remove(delpk)
                parent.childs = parentchilds
                parent.save()

        # Implement the following methods if you want to use a hierarchical
        # structure for curves
        @property
        def childs(self):
            try:
                return CurveDB.get(self.params["childs"])
            except KeyError:
                return []

        @property
        def parent(self):
            try:
                parentid = self.params["parent"]
            except KeyError:
                self.logger.debug("No parent found.")
                return None
            else:
                return CurveDB.get(parentid)

        def add_child(self, child_curve):
            child = CurveDB.get(child_curve)
            child.params["parent"] = self.pk
            child.save()
            childs = self.params["childs"] or []
            self.params["childs"] = list(childs+[child.pk])
            self.save()

        @classmethod
        def all(cls):
            pks = [int(f.split('.p')[0])
                   for f in os.listdir(cls._dirname) if f.endswith('.p')]
            return sorted(pks, reverse=True)

        @property
        def pk(self):
            if hasattr(self, "_pk"):
                return self._pk
            else:
                pks = self.all()
                if len(pks) == 0:
                    self._pk = 1
                else:
                    self._pk = max(pks) + 1
                # create the file to make this pk choice persistent
                with open(os.path.join(self._dirname,
                                       str(self._pk) + ".p"), 'w') as f:
                    f.close()
                return self._pk
            return -1
            # a proper implementation will assign the database primary key for pk
            # the primary key is used to load a curve from the storage into memory

        def sort(self):
            """numerically sorts the data series so that indexing can be used"""
            X, Y = self.data.index.values, self.data.values
            xs = np.array([x for (x, y) in sorted(zip(X, Y))], dtype=np.float64)
            ys = np.array([y for (x, y) in sorted(zip(X, Y))], dtype=np.float64)
            self.data = pandas.Series(ys, index=xs)

        def fit(self):
            """ prototype for fitting a curve """
            self.logger.warning("Not implemented")
            pass

        def get_child(self, name):
            """
            Returns the child of the curve with name 'name'

            ----------
            name: str
                Name of the child curve to be retrieved. If several childs
                have the same name, the first one is returned.

            Returns
            -------
            CurveDB: the child curve
            """
            for c in self.childs:
                if c.name == name:
                    return c
