Directory for user data "PYRPL\_USER\_DIR"
**********************************************

By default, PyRPL will search the home folder ":code:`HOME`" of the user
and create the folder ":code:`HOME`/pyrpl\_user\_dir". This folder
contains three subfolders:

    * :code:`config` for the PyRPL configuration files of the user.
    * :code:`lockbox` for custom lockbox scripts, similar to the files "interferometer.py" or "custom\_lockbox\_example.py".
    * :code:`curve` for saved curves / measurement data.

By setting the environment variable :code:`PYRPL_USER_DIR` to an existing
path on the file system, the location of the PyRPL user directory can be
modified. This is useful when the user data should be syncronized with a
designated github repository, for example.
