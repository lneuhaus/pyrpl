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
import pandas
import pickle
import os


class CurveDB(object):
    def __init__(self,name="some_curve"):
        """
        A CurveDB object has
        - name   = string to give the curve a name
        - pk     = integer to uniquely identify the curve (the database primary key)
        - data   = pandas.Series() object to hold any data
        - params = dict() with all kinds of parameters 
        """
        self.params = dict()
        self.data = pandas.Series()
        self.name = name
    
    @classmethod
    def create(cls, *args, **kwds):
        """
        Creates a new curve, first arguments should be either Series(y,index=x) or x, y 
        kwds will be passed to self.params
        """
        if len(args)==1:
            if isinstance(args[0], pandas.Series):
                ser = args[0]
            else:
                y = numpy.array(args[0])
                ser = pandas.Series(y)
        elif len(args)==2:
            x = numpy.array(args[0])
            y = numpy.array(args[1])
            ser = pandas.Series(y, index=x)
        else:
            raise ValueError("first arguments should be either x or x, y")
        obj = cls()
        obj.data = ser
        obj.params = kwds
        pk = self.pk #make a pk
        obj.save()
        return obj
    
    def plot(self):
        self.data.plot()

    
### Implement the following methods if you want to save curves permanently     
    @classmethod
    def get(cls, curve):
        if isinstance(curve,CurveDB):
            return curve
        else:
            with open(self._dirname+str(self.pk)+'.p','r') as f:
                curve = pickle.load(f)
            return curve
        print "Could not retrieve curve ",curve,"- not implemented yet!"
        return None
    
    def save(self):
        with open(self._dirname+str(self.pk)+'.p','w') as f:
            pickle.dump(self,f)
            f.close()
        #print "Save method not implemented yet. Therefore we will just plot the curve..."
        #self.plot()
        
    def delete(self):
        os.remove(self._dirname+str(self.pk)+'.p')

### Implement the following methods if you want to use a hierarchical structure for curves     
    @property
    def childs(self):
        print "Hierarchy not implemented."
        return []
        
    @property
    def parent(self):
        print "Hierarchy not implemented."
        return None

    def add_child(self,child_curve):
        print child_curve.name,"should be child of",self.name
        print "Curve hierarchy not implemented yet"
    
    @property
    def pk(self):
        if hasattr("_pk",self):
            return self._pk
        else:
            pks = [int(split(f,'.p')[0]) for f in os.listdir(self._dirname) if f.endswith('.p')]
            if len(pks) == 0:
                self._pk = 1
            else:
                self._pk = max(pks) + 1
            with open(self._dirname+str(self._pk)+".p",'w') as f: #create the file to make this pk choice persistent
                f.close()
            return self._pk
        return -1
         # a proper implementation will assign the database primary key for pk
         # the primary key is used to load a curve from the storage into memory

    @property
    def _dirname(self):
        import CurveDB
        return os.path.dirname(CurveDB.__file__)+"//curves//"
