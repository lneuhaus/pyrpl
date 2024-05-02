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
import pandas as pd
import os
import logging
import pickle as file_backend
#import json as file_backend  # currently unable to store pandas


# optional override of CurveDB class with custom module, as defined in
# ./pyrpl/config/global_config.yml
try:
    from . import global_config
    CurveDB = __import__(global_config.general.curvedb).CurveDB
except:
    from . import user_curve_dir
    class CurveDB(object):
        _dirname = user_curve_dir
        file_extension = '.dat'

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
            x, y = np.array([], dtype=float), np.array([], dtype=float)
            self.data = (x, y)
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
            if len(args) == 0:
                ser = (np.array([], dtype=float), np.array([], dtype=float))
            if len(args) == 1:
                if isinstance(args[0], pd.Series):
                    x, y = args[0].index.values, args[0].values
                    ser = (x, y)
                elif isinstance(args[0], (np.array, list, tuple)):
                    ser = args[0]
                else:
                    raise ValueError("cannot recognize argument %s as numpy.array or pandas.Series.", args[0])
            elif len(args) == 2:
                x = np.array(args[0])
                y = np.array(args[1])
                ser = (x, y)
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
            x, y = self.data
            pd.Series(y, index=x).plot()

        # Implement the following methods if you want to save curves permanently
        @classmethod
        def get(cls, curve):
            if isinstance(curve, CurveDB):
                return curve
            elif isinstance(curve, list):
                return [CurveDB.get(c) for c in curve]
            else:
                with open(os.path.join(CurveDB._dirname, str(curve) + cls.file_extension),
                          'rb' if file_backend.__name__ == 'pickle' else 'r')\
                        as f:
                    # rb is for compatibility with python 3
                    # see http://stackoverflow.com/questions/5512811/builtins-typeerror-must-be-str-not-bytes
                    curve = CurveDB()
                    curve._pk, curve.params, data = file_backend.load(f)
                    curve.data = tuple([np.asarray(a) for a in data])
                if isinstance(curve.data, pd.Series):  # for backwards compatibility
                    x, y = curve.data.index.values, curve.data.values
                    curve.data = (x, y)
                return curve

        def save(self):
            with open(os.path.join(self._dirname, str(self.pk) + self.file_extension),
                      'wb' if file_backend.__name__ == 'pickle' else 'w')\
                    as f:
                # wb is for compatibility with python 3
                # see http://stackoverflow.com/questions/5512811/builtins-typeerror-must-be-str-not-bytes
                data = [a.tolist() for a in self.data]
                file_backend.dump([self.pk, self.params, data], f, )

        def delete(self):
            # remove the file
            delpk = self.pk
            parent = self.parent
            childs = self.childs
            if isinstance(childs, list) and len(childs)> 0:
                self.logger.debug("Deleting all childs of curve %d"%delpk)
                for child in childs:
                    child.delete()
            self.logger.debug("Deleting curve %d" % delpk)
            try:
                filename = os.path.join(self._dirname, str(self.pk) + self.file_extension)
                os.remove(filename)
            except OSError:
                self.logger.warning("Could not find and remove the file %s. ",
                                    filename)
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
                childs = self.params["childs"]
            except KeyError:
                return []
            if childs is None:
                return []
            else:
                try:
                    return CurveDB.get(childs)
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
        def all_pks(cls):
            """
            Returns:
                list of int: A list of the primary keys of all CurveDB objects on the computer.
            """
            pks = [int(f.split('.dat')[0])
                   for f in os.listdir(cls._dirname) if f.endswith('.dat')]
            return sorted(pks, reverse=True)

        @classmethod
        def all(cls):
            """
            Returns:
                list of CurveDB: A list of all CurveDB objects on the computer.
            """
            return [cls.get(pk) for pk in cls.all_pks()]

        @property
        def pk(self):
            """
            (int): The primary Key of the
            """
            if hasattr(self, "_pk"):
                return self._pk
            else:
                pks = self.all_pks()
                if len(pks) == 0:
                    self._pk = 1
                else:
                    self._pk = max(pks) + 1
                # create the file to make this pk choice persistent
                with open(os.path.join(self._dirname,
                                       str(self._pk) + ".dat"), 'w') as f:
                    f.close()
                return self._pk
            return -1
            # a proper implementation will assign the database primary key for pk
            # the primary key is used to load a curve from the storage into memory

        def sort(self):
            """numerically sorts the data series so that indexing can be used"""
            X, Y = self.data
            xs = np.array([x for (x, y) in sorted(zip(X, Y))], dtype=np.float64)
            ys = np.array([y for (x, y) in sorted(zip(X, Y))], dtype=np.float64)
            self.data = (xs, ys)

        def fit(self):
            """ prototype for fitting a curve """
            self.logger.warning("Not implemented")
            pass

        def get_child(self, name):
            """
            Returns the child of the curve with name 'name'

            Arguments:
                name (str): Name of the child curve to be retrieved. If
                    several childs have the same name, the first one is
                    returned.

            Returns:
                CurveDB: the child curve
            """
            for c in self.childs:
                if c.name == name:
                    return c
