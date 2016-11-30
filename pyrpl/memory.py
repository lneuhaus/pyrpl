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

import logging
logger = logging.getLogger(name=__name__)

# the config file is read through a yaml interface. The preferred one is
# ruamel.yaml, since it allows to preserve comments and whitespace in the
# config file through roundtrips (the config file is rewritten every time a
# parameter is changed). If ruamel.yaml is not installed, the program will
# issue a warning and use pyyaml (=yaml= instead). Comments are lost in this
#  case.
try:
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
    def load(f):
        return ruamel.yaml.load(f, ruamel.yaml.RoundTripLoader)
    def save(data, stream=None):
        return ruamel.yaml.dump(data, stream=stream, Dumper=ruamel.yaml.RoundTripDumper, default_flow_style = False)
    def isbranch(obj):
        return isinstance(obj, dict) #type is ruamel.yaml.comments.CommentedMap
except:
    logger.warning("ruamel.yaml could not be found. Using yaml instead. Comments in config files will be lost.")
    import yaml
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
    def save(data, stream=None, Dumper=yaml.SafeDumper, default_flow_style=False, **kwds):
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
        return yaml.dump(data, stream, OrderedDumper,
                         default_flow_style=default_flow_style, **kwds)
    def isbranch(obj):
        return type(obj) == OrderedDict
    # usage example:
    # load(stream, yaml.SafeLoader)
    # save(data, stream=f, Dumper=yaml.SafeDumper)


class MemoryBranch(object):
    """Represents a branch of a memoryTree

    All methods are preceded by an underscore to guarantee that tab expansion
    of a memory branch only displays the available subbranches or leaves.


    Parameters
    ----------
    parent: MemoryBranch
        parent is the parent MemoryBranch
    branch: str
        branch is a string with the name of the branch to create
    defaults: list
        list of default branches that are used if requested data is not
        found in the current branch
    """
    def __init__(self, parent, branch, defaults=[]):
        self._branch = branch
        self._parent = parent
        self._defaults = defaults

    @property
    def _defaults(self):
        """ defaults allows to define a list of default branches to fall back
        upon if the desired key is not found in the current branch """
        return self.__defaults

    @_defaults.setter
    def _defaults(self, value):
        if isinstance(value, list):
            self.__defaults = list(value)
        else:
            self.__defaults = [value]
        # update __dict__ with inherited values from new defaults
        self.__dict__.update(self._dict)

    @property
    def _root(self):
        """ returns the parent highest in hierarchy (the MemoryTree object)"""
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

    def _getbranch(self, branchname, defaults=[]):
        """ returns a Memory branch from the same MemoryTree with
        branchname.
        Example: branchname = 'level1.level2.mybranch' """
        branch = self._root
        for subbranch in branchname.split('.'):
            branch = branch.__getattribute__(subbranch)
        branch._defaults = defaults
        return branch

    @property
    def _data(self):
        """ The raw data (OrderedDict) or Mapping of the branch """
        return self._parent._data[self._branch]

    @property
    def _dict(self):
        """ return a dict containing the memory branch data"""
        d = {}
        for defaultdict in reversed(self._defaults):
            d.update(defaultdict._dict)
        d.update(self._data)
        return d

    def _reload(self):
        """ reload data from file"""
        self._parent._reload()

    def _save(self):
        """ write data to file"""
        self._parent._save()

    def __getattribute__(self, name):
        """ implements the dot notation.
        Example: self.subbranch.leaf returns the item 'leaf' of 'subbranch' """
        if name.startswith('_'):
            return super(MemoryBranch, self).__getattribute__(name)
        else:
            # if subbranch, return MemoryBranch object
            if isbranch(self[name]):
                # test if we have a LemoryLeaf
                if 'value' in self[name]:
                    return self[name]['value']
                    # return MemoryLeaf(self, name) # maybe for the future
                # otherwise create a MemoryBranch object
                else:
                    return MemoryBranch(self, name)
            # otherwise return whatever we find in the data dict
            else:
                return self[name]

    # getitem bypasses the higher-level __getattribute__ function and provides
    # direct low-level access to the underlying dictionary.
    # This is much faster, as long as no changes have been made to the config
    # file.
    def __getitem__(self, item):
        self._reload()
        try:
            return self._data[item]
        except KeyError:
            for defaultbranch in self._defaults:
                if item in defaultbranch._data:
                    return defaultbranch._data[item]
            raise

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super(MemoryBranch, self).__setattr__(name, value)
        else:
            if isbranch(self._data[name]) and 'value' in self._data[name]:
                ro = self._data[name]["ro"] or False
                if ro:
                    logger.info("Attribute %s is read-only. New value %s cannot be written to config file",
                                name, value)
                else:
                    self._data[name]['value'] = value
            else:
                self._data[name] = value
            self._save()

    # creates a new entry, overriding the protection provided by dot notation
    # if the value of this entry is of type dict, it becomes a MemoryBranch
    # new values can be added to the branch in the same manner
    def __setitem__(self, item, value):
        if item in self._data:
            self.__setattr__(item, value)
        else:
            self._data[item] = value
            self._save()

    # remove an item from the config file
    def _pop(self, name):
        ro = isbranch(self._data[name]) and 'value' in self._data[name] and \
             (self._data[name]["ro"] or False)
        if ro:
            logger.info(
                "Attribute %s is read-only and cannot be deleted", name)
            return None
        else:
            self.__dict__.pop(name)
            value = self._data.pop(name)
            self._save()
            return value

    def __repr__(self):
        return "MemoryBranch("+str(self._dict.keys())+")"

    def _keys(self):
        return self._data.keys()


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
    _data = OrderedDict()
    # never reload more frequently than every 2 s because this is the principal
    # cause of slowing down the code
    _reloaddeadtime = 2

    def __init__(self, filename):
        if os.path.isfile(filename):
            self._filename = filename
        else:
            logger.warning("File "+filename+" not found. New file created. ")
            self._filename = filename
            with open(self._filename, mode="w") as f:
                pass
        self._load()
        super(MemoryTree, self).__init__(self, "")

    def _load(self):
        """ loads data from file """
        logger.debug("Loading config file %s", self._filename)
        with open(self._filename) as f:
            self._data = load(f)
        # update dict of the object
        for name in self.__dict__:
            if not name.startswith('_') and name not in self._data:
                self.__dict__.pop(name)
        self.__dict__.update(self._data)
        self._mtime = os.path.getmtime(self._filename)
        self._lastreload = time.time()

    def _reload(self):
        """" reloads data from file if file has changed recently """
        # first check if a reload was not performed recently (speed up reasons)
        if self._lastreload + self._reloaddeadtime < time.time():
            logger.debug("Checking change time of config file...")
            self._lastreload = time.time()
            if self._mtime != os.path.getmtime(self._filename):
                self._load()

    def _save(self):
        """ writes current tree structure and data to file """
        if self._mtime != os.path.getmtime(self._filename):
            logger.warning("Config file has recently been changed on your " +
                           "harddisk. These changes might have been " +
                           "overwritten now.")
        logger.debug("Saving config file %s", self._filename)
        copyfile(self._filename, self._filename+".bak")
        try:
            with open(self._filename, mode='w') as f:
                save(self._data, stream=f)
        except:
            copyfile(self._filename+".bak", self._filename)
            logger.error("Error writing to file. Backup version was restored.")
            raise
        self._mtime = os.path.getmtime(self._filename)

