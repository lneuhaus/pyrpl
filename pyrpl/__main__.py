"""
Script to launch pyrpl from the command line.

Type python -m pyrpl [config_file_name] to create
a Pyrpl instance with the config file
"config_file_name"
"""
import sys
try:
    from pyrpl import Pyrpl, APP, help_message
except:
    from . import Pyrpl, APP, help_message

if __name__ == '__main__':
    if len(sys.argv) > 3:
        print("usage: python run_pyrpl.py [[config=]config_file_name] "
              "[source=config_file_template] [hostname=hostname/ip]")
    kwargs = dict()
    for i, arg in enumerate(sys.argv):
        print (i, arg)
        if i == 0:
            continue
        try:
            k, v = arg.split('=', 1)
        except ValueError:
            k, v = arg, ""
        if v == "":
            if i == 1:
                kwargs["config"] = k
        else:
            kwargs[k] = v
    #APP = QtWidgets.QApplication.instance()
    #if APP is None:
    #    APP = QtWidgets.QApplication(sys.argv)

    if '--help' in kwargs:
        print(help_message)
    else:
        print("Calling Pyrpl(**%s)"%str(kwargs))
        PYRPL = Pyrpl(**kwargs)
        APP.exec_()
