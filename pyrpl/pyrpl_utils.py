import time
import logging

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
    all_names = [cls.section_name for cls in cls_list]
    names_set = set(all_names)
    names = []
    names_dict = dict(zip(names_set, [0]*len(names_set)))
    for name in all_names:
        if all_names.count(name) > 1:
            names_dict[name] += 1
            name += str(names_dict[name])
            names.append(name)
        else:
            names.append(name)
    return names


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

