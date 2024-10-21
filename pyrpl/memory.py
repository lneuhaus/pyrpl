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

import os
from collections import OrderedDict
from shutil import copyfile
import numpy as np
import time
from qtpy import QtCore
from . import default_config_dir, user_config_dir
from .pyrpl_utils import time

import logging
logger = logging.getLogger(name=__name__)


class UnexpectedSaveError(RuntimeError):
    pass
# the config file is read through a yaml interface. The preferred one is
# ruamel.yaml, since it allows to preserve comments and whitespace in the
# config file through roundtrips (the config file is rewritten every time a
# parameter is changed). If ruamel.yaml is not installed, the program will
# issue a warning and use pyyaml (=yaml= instead). Comments are lost in this
#  case.
try:
    raise  # disables ruamel support

    import ruamel.yaml
    #ruamel.yaml.add_implicit_resolver()
    ruamel.yaml.RoundTripDumper.add_representer(np.float64,
                lambda dumper, data: dumper.represent_float(float(data)))
    ruamel.yaml.RoundTripDumper.add_representer(complex,
                lambda dumper, data: dumper.represent_str(str(data)))
    ruamel.yaml.RoundTripDumper.add_representer(np.complex128,
                lambda dumper, data: dumper.represent_str(str(data)))
    ruamel.yaml.RoundTripDumper.add_representer(np.ndarray,
                lambda dumper, data: dumper.represent_list(list(data)))

    #http://stackoverflow.com/questions/13518819/avoid-references-in-pyyaml
    #ruamel.yaml.RoundTripDumper.ignore_aliases = lambda *args: True
    def load(f):
        return ruamel.yaml.load(f, ruamel.yaml.RoundTripLoader)
    def save(data, stream=None):
        return ruamel.yaml.dump(data, stream=stream,
                                Dumper=ruamel.yaml.RoundTripDumper,
                                default_flow_style=False)
except:
    logger.debug("ruamel.yaml could not be imported. Using yaml instead. "
                 "Comments in config files will be lost.")
    import yaml

    # see http://stackoverflow.com/questions/13518819/avoid-references-in-pyyaml
    #yaml.Dumper.ignore_aliases = lambda *args: True # NEVER TESTED

    # ordered load and dump for yaml files. From
    # http://stackoverflow.com/questions/5121931/in-python-how-can-you-load-yaml-mappings-as-ordereddicts
    def load(stream, Loader=yaml.SafeLoader, object_pairs_hook=OrderedDict):
        class OrderedLoader(Loader):
            pass
        def construct_mapping(loader, node):
            loader.flatten_mapping(node)
            return object_pairs_hook(loader.construct_pairs(node))
        OrderedLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            construct_mapping)
        return yaml.load(stream, OrderedLoader)
    def save(data, stream=None, Dumper=yaml.SafeDumper,
             default_flow_style=False,
             encoding='utf-8',
             **kwds):
        class OrderedDumper(Dumper):
            pass
        def _dict_representer(dumper, data):
            return dumper.represent_mapping(
                yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                data.items())
        OrderedDumper.add_representer(OrderedDict, _dict_representer)
        OrderedDumper.add_representer(np.float64,
                    lambda dumper, data: dumper.represent_float(float(data)))
        OrderedDumper.add_representer(complex,
                    lambda dumper, data: dumper.represent_str(str(data)))
        OrderedDumper.add_representer(np.complex128,
                    lambda dumper, data: dumper.represent_str(str(data)))
        OrderedDumper.add_representer(np.ndarray,
                    lambda dumper, data: dumper.represent_list(list(data)))
        # I added the following two lines to make pyrpl compatible with pyinstruments. In principle they can be erased
        if isinstance(data, dict) and not isinstance(data, OrderedDict):
            data = OrderedDict(data)
        return yaml.dump(data,
                         stream=stream,
                         Dumper=OrderedDumper,
                         default_flow_style=default_flow_style,
                         encoding=encoding,
                         **kwds)

    # usage example:
    # load(stream, yaml.SafeLoader)
    # save(data, stream=f, Dumper=yaml.SafeDumper)


def isbranch(obj):
    return isinstance(obj, dict) or isinstance(obj, list)


# two functions to locate config files
def _get_filename(filename=None):
    """ finds the correct path and name of a config file """
    # accidentally, we may pass a MemoryTree object instead of file
    if isinstance(filename, MemoryTree):
        return filename._filename
    # get extension right
    if not filename.endswith(".yml"):
        filename = filename + ".yml"
    # see if filename is found with given path, or in user_config or in default_config
    p, f = os.path.split(filename)
    for path in [p, user_config_dir, default_config_dir]:
        file = os.path.join(path, f)
        if os.path.isfile(file):
            return file
    # file not existing, place it in user_config_dir
    return os.path.join(user_config_dir, f)


def get_config_file(filename=None, source=None):
    """ returns the path to a valid, existing config file with possible source specification """
    # if None is specified, that means we do not want a persistent config file
    if filename is None:
        return filename
    # try to locate the file
    filename = _get_filename(filename)
    if os.path.isfile(filename):  # found a file
        p, f = os.path.split(filename)
        if p == default_config_dir:
            # check whether path is default_config_dir and make a copy in
            # user_config_dir in order to not alter original files
            dest = os.path.join(user_config_dir, f)
            copyfile(filename, dest)
            return dest
        else:
            return filename
    # file not existing, try to get it from source
    if source is not None:
        source = _get_filename(source)
        if os.path.isfile(source):  # success - copy the source
            logger.debug("File " + filename + " not found. New file created from source '%s'. "%source)
            copyfile(source,filename)
            return filename
    # still not returned -> create empty file
    with open(filename, mode="w"):
        pass
    logger.debug("File " + filename + " not found. New file created. ")
    return filename


class MemoryBranch(object):
    """Represents a branch of a memoryTree

    All methods are preceded by an underscore to guarantee that tab
    expansion of a memory branch only displays the available subbranches or
    leaves. A memory tree is a hierarchical structure. Nested dicts are
    interpreted as subbranches.

    Parameters
    ----------
    parent: MemoryBranch
        parent is the parent MemoryBranch
    branch: str
        branch is a string with the name of the branch to create
    defaults: list
        list of default branches that are used if requested data is not
        found in the current branch

    Class members
    -----------
    all properties without preceeding underscore are config file entries

    _data:      the raw data underlying the branch. Type depends on the
                loader and can be dict, OrderedDict or CommentedMap
    _dict:      similar to _data, but the dict contains all default
                branches
    _defaults:  list of MemoryBranch objects in order of decreasing
                priority that are used as defaults for the Branch.
                Changing the default values from the software will replace
                the default values in the current MemoryBranch but not
                alter the underlying default branch. Changing the
                default branch when it is not overridden by the current
                MemoryBranch results in an effective change in the branch.
    _keys:      same as _dict._keys()
    _update:    updates the branch with another dict
    _pop:       removes a value/subbranch from the branch
    _root:      the MemoryTree object (root) of the tree
    _parent:    the parent of the branch
    _branch:    the name of the branch
    _get_or_create: creates a new branch and returns it. Same as branch[newname]=dict(), but also supports nesting,
                e.g. newname="lev1.lev2.level3"
    _fullbranchname: returns the full path from root to the branch
    _getbranch: returns a branch by specifying its path, e.g. 'b1.c2.d3'
    _rename:    renames the branch
    _reload:    attempts to reload the data from disc
    _save:      attempts to save the data to disc

    If a subbranch or a value is requested but does not exist in the current MemoryTree, a KeyError is raised.
    """

    def __init__(self, parent, branch):
        self._parent = parent
        self._branch = branch
        self._update_instance_dict()

    def _update_instance_dict(self):
        data = self._data
        if isinstance(data, dict):
            for k in self.__dict__.keys():
                if k not in data and not k.startswith('_'):
                    self.__dict__.pop(k)
            for k in data.keys():
                # write None since this is only a
                # placeholder (__getattribute__ is overwritten below)
                self.__dict__[k] = None

    @property
    def _data(self):
        """ The raw data (OrderedDict) or Mapping of the branch """
        return self._parent._data[self._branch]

    @_data.setter
    def _data(self, value):
        logger.warning("You are directly modifying the data of MemoryBranch"
                       " %s to %s.", self._fullbranchname, str(value))
        self._parent._data[self._branch] = value

    def _keys(self):
        if isinstance(self._data, list):
            return range(self.__len__())
        else:
            return self._data.keys()

    def _update(self, new_dict):
        if isinstance(self._data, list):
            raise NotImplementedError
        self._data.update(new_dict)
        self._save()
        # keep auto_completion up to date
        for k in new_dict:
            self.__dict__[k] = None

    def __getattribute__(self, name):
        """ implements the dot notation.
        Example: self.subbranch.leaf returns the item 'leaf' of 'subbranch' """
        if name.startswith('_'):
            return super(MemoryBranch, self).__getattribute__(name)
        else:
            # convert dot notation into dict notation
            return self[name]

    def __getitem__(self, item):
        """
        __getitem__ bypasses the higher-level __getattribute__ function and provides
        direct low-level access to the underlying dictionary.
        This is much faster, as long as no changes have been made to the config
        file.
        """
        self._reload()
        # if a subbranch is requested, iterate through the hierarchy
        if isinstance(item, str) and '.' in item:
            item, subitem = item.split('.', 1)
            return self[item][subitem]
        else:  # otherwise just return what we can find
            attribute = self._data[item]  # read from the data dict
            if isbranch(attribute):  # if the object can be expressed as a branch, do so
                return MemoryBranch(self, item)
            else:  # otherwise return whatever we found in the data dict
                return attribute

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super(MemoryBranch, self).__setattr__(name, value)
        else:  # implemment dot notation
            self[name] = value

    def __setitem__(self, item, value):
        """
        creates a new entry, overriding the protection provided by dot notation
        if the value of this entry is of type dict, it becomes a MemoryBranch
        new values can be added to the branch in the same manner
        """
        # if the subbranch is set or replaced, to this in a specific way
        if isbranch(value):
            # naive way: self._data[item] = dict(value)
            # rather: replace values in their natural order (e.g. if value is OrderedDict)
            # make an empty subbranch
            if isinstance(value, list):
                self._set_data(item, [])
                subbranch = self[item]
                # use standard setter to set the values 1 by 1 and possibly as subbranch objects
                for k, v in enumerate(value):
                    subbranch[k] = v
            else:  # dict-like
                # makes an empty subbranch
                self._set_data(item, dict())
                subbranch = self[item]
                # use standard setter to set the values 1 by 1 and possibly as subbranch objects
                for k, v in value.items():
                    subbranch[k] = v
        #otherwise just write to the data dictionary
        else:
            self._set_data(item, value)
        if self._root._WARNING_ON_SAVE or self._root._ERROR_ON_SAVE:
            logger.warning("Issuing call to MemoryTree._save after %s.%s=%s",
                           self._branch, item, value)
        self._save()
        # update the __dict__ for autocompletion
        self.__dict__[item] = None

    def _set_data(self, item, value):
        """
        helper function to manage setting list entries that do not exist
        """
        if isinstance(self._data, list) and item == len(self._data):
            self._data.append(value)
        else:
            # trivial case: _data is dict or item within list length
            # and we can simply set the entry
            self._data[item] = value

    def _pop(self, name):
        """
        remove an item from the branch
        """
        value = self._data.pop(name)
        if name in self.__dict__.keys():
            self.__dict__.pop(name)
        self._save()
        return value

    def _rename(self, name):
        self._parent[name] = self._parent._pop(self._branch)
        self._save()

    def _get_or_create(self, name):
        """
        creates a new subbranch with name=name if it does not exist already
        and returns it. If name is a branch hierarchy such as
        "subbranch1.subbranch2.subbranch3", all three subbranch levels
        are created
        """
        if isinstance(name, int):
            if name == 0 and len(self) == 0:
                # instantiate a new list - odd way because we must
                self._parent._data[self._branch] = []
            # if index <= len, creation is done automatically if needed
            # otherwise an error is raised
            if name >= len(self):
                self[name] = dict()
            return self[name]
        else:  # dict-like subbranch, support several sublevels separated by '.'
            # chop name into parts and iterate through them
            currentbranch = self
            for subbranchname in name.split("."):
                # make new branch if applicable
                if subbranchname not in currentbranch._data.keys():
                    currentbranch[subbranchname] = dict()
                # move into new branch in case another subbranch will be created
                currentbranch = currentbranch[subbranchname]
            return currentbranch

    def _erase(self):
        """
        Erases the current branch
        """
        self._parent._pop(self._branch)
        self._save()

    @property
    def _root(self):
        """
        returns the parent highest in hierarchy (the MemoryTree object)
        """
        parent = self
        while parent != parent._parent:
            parent = parent._parent
        return parent

    @property
    def _fullbranchname(self):
        parent = self._parent
        branchname = self._branch
        while parent != parent._parent:
            branchname = parent._branch + '.' + branchname
            parent = parent._parent
        return branchname

    def _reload(self):
        """ reload data from file"""
        self._parent._reload()

    def _save(self):
        """ write data to file"""
        self._parent._save()

    def _get_yml(self, data=None):
        """
        :return: returns the yml code for this branch
        """
        return save(self._data if data is None else data).decode('utf-8')

    def _set_yml(self, yml_content):
        """
        :param yml_content: sets the branch to yml_content
        :return: None
        """
        branch = load(yml_content)
        self._parent._data[self._branch] = branch
        self._save()

    def __len__(self):
        return len(self._data)

    def __contains__(self, item):
        return item in self._data

    def __repr__(self):
        return "MemoryBranch(" + str(self._keys()) + ")"

    def __add__(self, other):
        """
        makes it possible to add list-like memory tree to a list
        """
        if not isinstance(self._data, list):
            raise NotImplementedError
        return self._data + other

    def __radd__(self, other):
        """
        makes it possible to add list-like memory tree to a list
        """
        if not isinstance(self._data, list):
            raise NotImplementedError
        return other + self._data


class MemoryTree(MemoryBranch):
    """
    The highest level of a MemoryBranch construct. All attributes of this
    object that do not start with '_' are other MemoryBranch objects or
    Leaves, i.e. key - value pairs.

    Parameters
    ----------
    filename: str
        The filename of the .yml file defining the MemoryTree structure.
    """
    ##### internal load logic:
    # 1. initially, call _load() to get the data from the file
    # 2. upon each inquiry of the config data, _reload() is called to
    # ensure data integrity
    # 3. _reload assumes a delay of _loadsavedeadtime between changing the
    # config file and Pyrpl requesting the new data. That means, _reload
    # will not attempt to touch the config file more often than every
    # _loadsavedeadtime. The last interaction time with the file system is
    # saved in the variable _lastreload. If this time is far enough in the
    # past, the modification time of the config file is compared to _mtime,
    # the internal memory of the last modifiation time by pyrpl. If the two
    # don't match, the file was altered outside the scope of pyrpl and _load
    # is called to reload it.

    ##### internal save logic:

    # this structure will hold the data. Must define it here as immutable
    # to overwrite the property _data of MemoryBranch
    _data = None

    _WARNING_ON_SAVE = False  # flag that is used to debug excessive calls to
    # save
    _ERROR_ON_SAVE = False # Set this flag to true to raise
        # Exceptions upon save

    def __init__(self, filename=None, source=None, _loadsavedeadtime=3):
        # never reload or save more frequently than _loadsavedeadtime because
        # this is the principal cause of slowing down the code (typ. 30-200 ms)
        # for immediate saving, call _save_now, for immediate loading _load_now
        self._loadsavedeadtime = _loadsavedeadtime
        # first, make sure filename exists
        self._filename = get_config_file(filename, source)
        if filename is None:
            # to simulate a config file, only store data in memory
            self._filename = filename
            self._data = OrderedDict()
        self._lastsave = time()
        # create a timer to postpone to frequent savings
        self._savetimer = QtCore.QTimer()
        self._savetimer.setInterval(self._loadsavedeadtime*1000)
        self._savetimer.setSingleShot(True)
        self._savetimer.timeout.connect(self._write_to_file)
        self._load()

        self._save_counter = 0 # cntr for unittest and debug purposes
        self._write_to_file_counter = 0  # cntr for unittest and debug purposes

        # root of the tree is also a MemoryBranch with parent self and
        # branch name ""
        super(MemoryTree, self).__init__(self, "")

    @property
    def _buffer_filename(self):
        """ makes a temporary file to ensure modification of config file is atomic (double-buffering like operation...)"""
        return self._filename + '.tmp'

    def _load(self):
        """ loads data from file """
        if self._filename is None:
            # if no file is used, just ignore this call
            return
        logger.debug("Loading config file %s", self._filename)
        # read file from disc
        with open(self._filename) as f:
            self._data = load(f)
        # store the modification time of this file version
        self._mtime = os.path.getmtime(self._filename)
        # make sure that reload timeout starts from this moment
        self._lastreload = time()
        # empty file gives _data=None
        if self._data is None:
            self._data = OrderedDict()
        # update dict of the MemoryTree object
        to_remove = []
        # remove all obsolete entries
        for name in self.__dict__:
            if not name.startswith('_') and name not in self._data:
                to_remove.append(name)
        for name in to_remove:
            self.__dict__.pop(name)
        # insert the branches into the object __dict__ for auto-completion
        self.__dict__.update(self._data)

    def _reload(self):
        """
        reloads data from file if file has changed recently
        """
        # first check if a reload was not performed recently (speed up reasons)
        if self._filename is None:
            return
        # check whether reload timeout has expired
        if time() > self._lastreload + self._loadsavedeadtime:
            # prepare next timeout
            self._lastreload = time()
            logger.debug("Checking change time of config file...")
            if self._mtime != os.path.getmtime(self._filename):
                logger.debug("Loading because mtime %s != filetime %s",
                             self._mtime)
                self._load()
            else:
                logger.debug("... no reloading required")

    def _write_to_file(self):
        """
        Immmediately writes the content of the memory tree to file
        """
        # stop save timer
        if hasattr(self, '_savetimer') and self._savetimer.isActive():
            self._savetimer.stop()
        self._lastsave = time()
        self._write_to_file_counter += 1
        logger.debug("Saving config file %s", self._filename)
        if self._filename is None:
            # skip writing to file if no filename was selected
            return
        else:
            if self._mtime != os.path.getmtime(self._filename):
                logger.warning("Config file has recently been changed on your " +
                               "harddisk. These changes might have been " +
                               "overwritten now.")
            # we must be sure that overwriting config file never destroys existing data.
            # security 1: backup with copyfile above
            copyfile(self._filename,
                     self._filename + ".bak")  # maybe this line is obsolete (see below)
            # security 2: atomic writing such as shown in
            # http://stackoverflow.com/questions/2333872/atomic-writing-to-file-with-python:
            try:
                f = open(self._buffer_filename, mode='w')
                save(self._data, stream=f)
                f.flush()
                os.fsync(f.fileno())
                f.close()
                os.unlink(self._filename)
                os.rename(self._buffer_filename, self._filename)
            except:
                copyfile(self._filename + ".bak", self._filename)
                logger.error("Error writing to file. Backup version was restored.")
                raise
            # save last modification time of the file
            self._mtime = os.path.getmtime(self._filename)

    def _save(self, deadtime=None):
        """
        A call to this function means that the state of the tree has changed
        and needs to be saved eventually. To reduce system load, the delay
        between two writes will be at least deadtime (defaults to
        self._loadsavedeadtime if None)
        """
        if self._ERROR_ON_SAVE:
            raise UnexpectedSaveError("Save to config file should not "
                                      "happen now")
        if self._WARNING_ON_SAVE:
            logger.warning("Save counter has just been increased to %d.",
                           self._save_counter)
        self._save_counter += 1  # for unittest and debug purposes
        if deadtime is None:
            deadtime = self._loadsavedeadtime
        # now write current tree structure and data to file
        if self._lastsave + deadtime < time():
            self._write_to_file()
        else:
            # make sure saving will eventually occur by launching a timer
            if not self._savetimer.isActive():
                self._savetimer.start()

    @property
    def _filename_stripped(self):
        try:
            return os.path.split(self._filename)[1].split('.')[0]
        except:
            return 'default'
