if False:
    from distutils.core import setup
    import py2exe

    #setup(console=['test_exe.py'])
    setup(console=['run_pyrpl.py'])
else:
    import sys
    from cx_Freeze import setup, Executable

    # Dependencies are automatically detected, but it might need fine tuning.
    build_exe_options = {}#{"packages": ["os"], "excludes": ["tkinter"]}

    # GUI applications require a different base on Windows (the default is
    # for a
    # console application).
    base = None
    if sys.platform == "win32":
        base = "Win32GUI"

    setup(name="run_pyrpl",
          version="0.9.3.1",
          description="My GUI application!",
          options={"build_exe": build_exe_options},
          executables=[Executable("run_pyrpl.py", base=base)])
