import time
from timeit import default_timer
import logging
logger = logging.getLogger(__file__)
from collections import OrderedDict, Counter

# global variable that tells whether QT is available - should be deprecated since we have a hard dependence on QT
QT_EXIST = True
try:
    from PyQt4 import QtCore, QtGui
except ImportError:
    QT_EXIST = False
if QT_EXIST:
    APP = QtGui.QApplication.instance()

def sleep(time_s):
    """
    If PyQt4 is installed on the machine,
    calls processEvents regularly to make sure
     the GUI doesn't freeze.

     This function should be used everywhere in the
     project in place of "time.sleep"
    """
    # QTimer-based sleep operation is not to be used for now
    if False: #QT_EXIST and APP is not None:
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.setInterval(1000*time_s)
        timer.start()
        while(timer.isActive()):
            APP.processEvents()
    else:
        time.sleep(time_s)

def time():
    """ returns the time. used instead of time.time for rapid portability"""
    return default_timer()

def get_unique_name_list_from_class_list(cls_list):
    """
    returns a list of names using cls.name if unique or cls.name1, cls.name2... otherwise.
    Order of the name list matches order of cls_list, such that iterating over zip(cls_list, name_list) is OK
    """
    # cls_list is typically
    # cls_modules = [rp.HK, rp.AMS, rp.Scope, rp.Sampler, rp.Asg1, rp.Asg2] + \
    #              [rp.AuxOutput] * 2 + [rp.IQ] * 3 + [rp.Pid] * 4 + [rp.IIR]

    # first, map from list of classes to a list of corresponding names
    # e.g. all_names = ['hk, ..., 'pwm', 'pwm', ...
    all_names = [cls.__name__.lower() for cls in cls_list]
    final_names = []
    for name in all_names:
        # how many times does the name occur?
        occurences = all_names.count(name)
        if occurences == 1:
            # for single names, leave as-is
            final_names.append(name)
        else:
            # for multiple name, assign name+str(lowest_free_number)
            for i in range(occurences):
                if not name+str(i) in final_names:
                    final_names.append(name+str(i))
                    break
    return final_names


def setloglevel(level='info', loggername='pyrpl'):
    """ sets the log level to the one specified in config file"""
    try:
        loglevels = {"notset": logging.NOTSET,
                     "debug": logging.DEBUG,
                     "info": logging.INFO,
                     "warning": logging.WARNING,
                     "error": logging.ERROR,
                     "critical": logging.CRITICAL}
        level = loglevels[level]
    except:
        pass
    else:
        logging.getLogger(name=loggername).setLevel(level)


def sorted_dict(dict_to_sort=None, sort_by_values=True, **kwargs):
    if dict_to_sort is None:
        dict_to_sort = kwargs
    if not sort_by_values:
        return OrderedDict(sorted(dict_to_sort.items()))
    else:
        return OrderedDict(sorted(dict_to_sort.items(), key=lambda x: x[1]))


def unique_list(nonunique_list):
    unique_list = []
    for attr in nonunique_list:
        if attr not in unique_list:
            unique_list.append(attr)
    return unique_list


class Bijection(dict):
    """ This class defines a bijection object based on dict

    It can be used exactly like dict, but additionally has a property
    'inverse' which contains the inverted {value: key} dict. """

    def __init__(self, *args, **kwargs):
        super(Bijection, self).__init__(*args, **kwargs)
        self.inverse = {v: k for k, v in self.items()}

    def __setitem__(self, key, value):
        super(Bijection, self).__setitem__(key, value)
        self.inverse[value] = key

    def __delitem__(self, key):
        self.inverse.__delitem__(self.__getitem__(key))
        super(Bijection, self).__delitem__(key)

    def pop(self, key):
        self.inverse.pop(self.__getitem__(key))
        super(Bijection, self).pop(key)

    def update(self, *args, **kwargs):
        super(Bijection, self).update(*args, **kwargs)
        self.inverse = {v: k for k, v in self.items()}


def all_subclasses(cls):
    """ returns a list of all subclasses of cls """
    return cls.__subclasses__() + [g for s in cls.__subclasses__()
                                   for g in all_subclasses(s)]

