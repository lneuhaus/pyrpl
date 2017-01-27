import time
import logging
from collections import OrderedDict, Counter

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

    if QT_EXIST:
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.setInterval(1000*time_s)
        timer.start()
        while(timer.isActive()):
            APP.processEvents()
    else:
        time.sleep(time_s)

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
    all_names = [cls.section_name for cls in cls_list]
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

